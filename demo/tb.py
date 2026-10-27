"""Tinderbox 最小核心：L0 材料 + L1 摘要 + 中文检索 + 版本链。

零依赖：压缩用 gzip（有 zstandard 则自动用），分词用 bigram（有 jieba 则自动用）。
这两处正是方案里写的降级路径。
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ------------------------------------------------------------------ 日志
import logging
import logging.handlers

LOG = logging.getLogger("tinderbox")
LOG.addHandler(logging.NullHandler())
SECRET_PARTS = ("key", "token", "secret", "password", "authorization")


class _Line(logging.Formatter):
    """2026-10-27T17:00:00Z INFO  ingest  file=发货.md entries=2"""

    def format(self, r):
        ts = datetime.fromtimestamp(r.created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        name = r.name.split(".")[-1]
        return f"{ts} {r.levelname:<5} {name:<9} {r.getMessage()}"


def setup_logging(log_dir: Path, console_level: str = "WARN") -> Path:
    """文件日志（5 MB × 5 份轮转）+ 控制台。重复调用不叠加 handler。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "tinderbox.log"
    for h in list(LOG.handlers):
        LOG.removeHandler(h)
    fh = logging.handlers.RotatingFileHandler(path, maxBytes=5 * 1024 * 1024,
                                              backupCount=5, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_Line())
    LOG.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(_Line())
    ch.setLevel(getattr(logging, console_level.upper(), logging.WARNING))
    LOG.addHandler(ch)
    LOG.setLevel(logging.DEBUG)
    return path


def _kv(**kv) -> str:
    parts = []
    for k, v in kv.items():
        if any(x in k.lower() for x in SECRET_PARTS):
            v = "***"
        if isinstance(v, str) and (" " in v or "=" in v):
            v = f'"{v}"'
        parts.append(f"{k}={v}")
    return " ".join(parts)


def log_event(module: str, msg: str, **kv):
    logging.getLogger(f"tinderbox.{module}").handle(
        logging.LogRecord(f"tinderbox.{module}", logging.INFO, __file__, 0,
                          msg + (" " + _kv(**kv) if kv else ""), None, None))


def log_warn(module: str, msg: str, **kv):
    logging.getLogger(f"tinderbox.{module}").handle(
        logging.LogRecord(f"tinderbox.{module}", logging.WARNING, __file__, 0,
                          msg + (" " + _kv(**kv) if kv else ""), None, None))

DB_PATH = BASE / "out" / "memory.db"
ARCHIVE = BASE / "out" / "archive" / "l0"

try:
    import zstandard as zstd
    CODEC = "zstd"
except Exception:
    zstd = None
    CODEC = "gzip"

try:
    import jieba
    jieba.setLogLevel(60)
    TOKENIZER = "jieba"
except Exception:
    jieba = None
    TOKENIZER = "bigram"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def new_id(prefix: str) -> str:
    return f"{prefix}-{os.urandom(6).hex()}"


# ------------------------------------------------------------------ 压缩
def compress(data: bytes) -> bytes:
    if CODEC == "zstd":
        return zstd.ZstdCompressor(level=10).compress(data)
    return gzip.compress(data, compresslevel=9)


def decompress(data: bytes) -> bytes:
    if CODEC == "zstd":
        return zstd.ZstdDecompressor().decompress(data)
    return gzip.decompress(data)


# ------------------------------------------------------------------ 分词
_CJK = re.compile(r"[\u4e00-\u9fff]+")
_ALNUM = re.compile(r"[a-zA-Z0-9_]+")
_STOP = set("的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 这 那 他 她 它 我们 你们 他们".split())


try:                                     # 简繁归一：FTS 自己不做，必须在分词口统一
    from t2s import to_simplified as _to_simplified
except Exception:
    _to_simplified = None


def tokenize(text: str) -> list[str]:
    if _to_simplified:
        text = _to_simplified(text)
    text = text.lower()
    out: list[str] = []
    if TOKENIZER == "jieba":
        out = [t.strip() for t in jieba.cut_for_search(text)]
    else:
        # bigram：中文按二元切分，英文/数字整体保留
        for m in _CJK.finditer(text):
            run = m.group(0)
            if len(run) == 1:
                out.append(run)
            else:
                out.extend(run[i:i + 2] for i in range(len(run) - 1))
        out.extend(m.group(0) for m in _ALNUM.finditer(text))
    toks = [t for t in out if t and t not in _STOP and not t.isspace()]
    return list(dict.fromkeys(toks))


def tokenize_for_index(text: str) -> str:
    return " ".join(tokenize(text))


def build_match(query: str, mode: str = "and") -> str:
    toks = tokenize(query)
    if not toks:
        return ""
    quoted = ['"' + t.replace('"', '""') + '"' for t in toks]
    return (" AND " if mode == "and" else " OR ").join(quoted)


def content_hash(text: str, n: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


@contextmanager
def tx(conn):
    """可嵌套的写事务：外层 BEGIN IMMEDIATE，内层直接复用。"""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


# ------------------------------------------------------------------ 建库
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS memory_blobs(
    hash       TEXT PRIMARY KEY,
    path       TEXT NOT NULL,
    codec      TEXT NOT NULL,
    raw_size   INTEGER NOT NULL,
    size       INTEGER NOT NULL,
    ref_count  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_documents(
    doc_id          TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    title           TEXT,
    source          TEXT NOT NULL DEFAULT 'import',
    blob_hash       TEXT NOT NULL REFERENCES memory_blobs(hash),
    char_count      INTEGER NOT NULL,
    raw_size        INTEGER NOT NULL,
    compressed_size INTEGER NOT NULL,
    entry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    expires_at      TEXT
);

CREATE TABLE IF NOT EXISTS memory_groups(
    group_id           TEXT PRIMARY KEY,
    root_id            TEXT NOT NULL,
    user_id            TEXT NOT NULL,
    topic              TEXT,
    current_version_no INTEGER NOT NULL DEFAULT 1,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_entries(
    row_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id        TEXT NOT NULL UNIQUE,
    user_id         TEXT NOT NULL,
    memory_group_id TEXT NOT NULL REFERENCES memory_groups(group_id),
    root_id         TEXT NOT NULL,
    version_no      INTEGER NOT NULL DEFAULT 1,
    predecessor_id  TEXT,
    superseded_by   TEXT,
    category        TEXT NOT NULL,
    l1_summary      TEXT NOT NULL,
    tokenized       TEXT NOT NULL DEFAULT '',
    kw_tokens       TEXT NOT NULL DEFAULT '',
    keywords        TEXT NOT NULL DEFAULT '',
    context         TEXT NOT NULL DEFAULT '',   -- 前因：话题的来龙去脉（链首尤其需要）
    doc_id          TEXT REFERENCES memory_documents(doc_id),
    l0_offset       INTEGER,
    l0_length       INTEGER,
    chunk_index     INTEGER,
    confidence      TEXT NOT NULL DEFAULT 'medium',
    verified_at     TEXT,                              -- 人核对过的时间；决定原文保留档位
    verified_by     TEXT,
    extract_state   TEXT NOT NULL DEFAULT 'provisional',  -- provisional/refined/failed
    refined_at      TEXT,
    importance      REAL NOT NULL DEFAULT 0.5,
    status          TEXT NOT NULL DEFAULT 'active',
    pin             INTEGER NOT NULL DEFAULT 0,
    anchor          INTEGER NOT NULL DEFAULT 0,
    weight          REAL NOT NULL DEFAULT 1.0,
    access_count    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    last_accessed_at TEXT,
    UNIQUE(memory_group_id, version_no)
);

CREATE TABLE IF NOT EXISTS memory_conflicts(
    conflict_id  TEXT PRIMARY KEY,
    old_entry_id TEXT NOT NULL,
    new_entry_id TEXT NOT NULL,
    relation     TEXT NOT NULL,
    similarity   REAL NOT NULL,
    confidence   REAL,
    reason       TEXT,
    suggestion   TEXT,
    state        TEXT NOT NULL DEFAULT 'open',
    resolution   TEXT,
    created_at   TEXT NOT NULL,
    UNIQUE(old_entry_id, new_entry_id)
);

CREATE TABLE IF NOT EXISTS memory_concepts(
    concept_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    parent_id  TEXT REFERENCES memory_concepts(concept_id),
    level      INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- 多对多：一条记忆可以同时挂在「小节」和「项目」两个概念上
CREATE TABLE IF NOT EXISTS memory_entry_concepts(
    entry_id   TEXT NOT NULL,
    concept_id TEXT NOT NULL,
    PRIMARY KEY(entry_id, concept_id)
);

CREATE TABLE IF NOT EXISTS memory_relations(
    relation_id TEXT PRIMARY KEY,
    from_entry  TEXT NOT NULL,
    to_entry    TEXT NOT NULL,
    relation    TEXT NOT NULL,
    confidence  REAL,
    reason      TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE(from_entry, to_entry)
);

CREATE TABLE IF NOT EXISTS memory_revisions(
    revision_id TEXT PRIMARY KEY,
    entry_id    TEXT NOT NULL REFERENCES memory_entries(entry_id) ON DELETE CASCADE,
    old_summary TEXT NOT NULL,
    new_summary TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts_active USING fts5(
    entry_id UNINDEXED, tokenized, kw_tokens, tokenize='unicode61 remove_diacritics 2');

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts_history USING fts5(
    entry_id UNINDEXED, tokenized, kw_tokens, tokenize='unicode61 remove_diacritics 2');
"""

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_fts_ai AFTER INSERT ON memory_entries
WHEN NEW.tokenized <> ''
BEGIN
    INSERT INTO memory_fts_active(rowid, entry_id, tokenized, kw_tokens)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized, NEW.kw_tokens
         WHERE NEW.status IN ('active','pending_merge');
    INSERT INTO memory_fts_history(rowid, entry_id, tokenized, kw_tokens)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized, NEW.kw_tokens
         WHERE NEW.status IN ('superseded','archived');
END;

CREATE TRIGGER IF NOT EXISTS trg_fts_au
AFTER UPDATE OF status, tokenized ON memory_entries
WHEN OLD.status IS NOT NEW.status OR OLD.tokenized IS NOT NEW.tokenized
BEGIN
    DELETE FROM memory_fts_active  WHERE rowid = NEW.row_id;
    DELETE FROM memory_fts_history WHERE rowid = NEW.row_id;
    INSERT INTO memory_fts_active(rowid, entry_id, tokenized, kw_tokens)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized, NEW.kw_tokens
         WHERE NEW.status IN ('active','pending_merge') AND NEW.tokenized <> '';
    INSERT INTO memory_fts_history(rowid, entry_id, tokenized, kw_tokens)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized, NEW.kw_tokens
         WHERE NEW.status IN ('superseded','archived') AND NEW.tokenized <> '';
END;

CREATE TRIGGER IF NOT EXISTS trg_fts_ad AFTER DELETE ON memory_entries
BEGIN
    DELETE FROM memory_fts_active  WHERE rowid = OLD.row_id;
    DELETE FROM memory_fts_history WHERE rowid = OLD.row_id;
END;
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        ensure_columns(conn)
        ensure_tables(conn)
    except sqlite3.OperationalError:
        pass          # 全新库、表还没建：交给 init_db
    return conn


def init_db(reset: bool = False):
    if reset:
        for p in (DB_PATH, Path(str(DB_PATH) + "-wal"), Path(str(DB_PATH) + "-shm")):
            p.unlink(missing_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    conn.executescript(TRIGGERS)
    ensure_columns(conn)
    ensure_tables(conn)
    return conn


# ------------------------------------------------------------------ L0
AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS memory_audit(
    audit_id  TEXT PRIMARY KEY,
    at        TEXT NOT NULL,
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    entry_id  TEXT,
    detail    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_entry ON memory_audit(entry_id, at);
"""


def ensure_tables(conn) -> None:
    """只建不改：新增表在这里登记，connect 时自动补齐。"""
    conn.executescript(AUDIT_DDL)


def audit(conn, actor: str, action: str, entry_id: str = "", **detail) -> str:
    """记一条操作轨迹。永远不抛错——审计不能影响主流程。"""
    aid = new_id("au")
    try:
        conn.execute("INSERT INTO memory_audit(audit_id,at,actor,action,entry_id,detail)"
                     " VALUES (?,?,?,?,?,?)",
                     (aid, now(), actor, action, entry_id,
                      ", ".join(f"{k}={v}" for k, v in detail.items())))
    except Exception:
        pass
    return aid


def ensure_columns(conn) -> list[str]:
    """旧库补列。新增字段时在这里登记，启动即自动迁移。"""
    wanted = {
        "memory_entries": [("extract_state", "TEXT NOT NULL DEFAULT 'provisional'"),
                           ("refined_at", "TEXT"),
                           ("verified_at", "TEXT"),
                           ("verified_by", "TEXT"),
                           ("context", "TEXT NOT NULL DEFAULT ''"),
                             ("reason", "TEXT NOT NULL DEFAULT ''")],
        "memory_documents": [("expires_at", "TEXT")],
    }
    added = []
    for table, cols in wanted.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
                added.append(f"{table}.{name}")
    return added


def put_document(conn: sqlite3.Connection, text: str, *, user_id="owner",
                 title="", source="import") -> str:
    raw = text.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    row = conn.execute("SELECT hash, path FROM memory_blobs WHERE hash=?", (digest,)).fetchone()
    if row is None:
        rel = f"{digest[:2]}/{digest}.{ 'zst' if CODEC=='zstd' else 'gz'}"
        abspath = ARCHIVE / rel
        abspath.parent.mkdir(parents=True, exist_ok=True)
        blob = compress(raw)
        tmp = abspath.with_suffix(abspath.suffix + ".tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, abspath)
        conn.execute(
            "INSERT INTO memory_blobs(hash,path,codec,raw_size,size,ref_count,created_at)"
            " VALUES (?,?,?,?,?,1,?)",
            (digest, str(rel), CODEC, len(raw), len(blob), now()))
        path, size = str(rel), len(blob)
    else:
        path = row["path"]
        size = conn.execute("SELECT size FROM memory_blobs WHERE hash=?", (digest,)).fetchone()[0]
        conn.execute("UPDATE memory_blobs SET ref_count=ref_count+1 WHERE hash=?", (digest,))

    doc_id = new_id("d")
    conn.execute(
        "INSERT INTO memory_documents(doc_id,user_id,title,source,blob_hash,char_count,"
        "raw_size,compressed_size,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (doc_id, user_id, title or text[:20].replace("\n", " "), source,
         digest, len(text), len(raw), size, now()))
    return doc_id


def read_document(conn: sqlite3.Connection, doc_id: str) -> str:
    row = conn.execute(
        "SELECT d.blob_hash, b.path, b.codec FROM memory_documents d "
        "JOIN memory_blobs b ON b.hash=d.blob_hash WHERE d.doc_id=?", (doc_id,)).fetchone()
    if row is None:
        raise KeyError(doc_id)
    return decompress((ARCHIVE / row["path"]).read_bytes()).decode("utf-8")


def get_span(conn, entry_id: str, before: int = 80, after: int = 80) -> dict:
    row = conn.execute(
        "SELECT e.doc_id, e.l0_offset, e.l0_length, e.l1_summary "
        "FROM memory_entries e WHERE e.entry_id=?", (entry_id,)).fetchone()
    if row is None or row["doc_id"] is None:
        raise KeyError(entry_id)
    text = read_document(conn, row["doc_id"])
    lo = max(0, row["l0_offset"] - before)
    hi = min(len(text), row["l0_offset"] + row["l0_length"] + after)
    return {"doc_id": row["doc_id"], "offset": row["l0_offset"],
            "length": row["l0_length"], "text": text[lo:hi],
            "span": text[row["l0_offset"]:row["l0_offset"] + row["l0_length"]]}


# ------------------------------------------------------------------ 分块
_SENT_MARK = "。！？；!?;"


def _atoms(text: str, hard_max: int) -> list[tuple[int, int]]:
    """把文本拆成不超过 hard_max 的原子片段。

    优先用空行分段；**没有空行就按单行**（粘贴的聊天记录、PDF 文本都是这个形态）；
    单行仍然超长就按句末标点切。三者都没有才硬切——顺序不能反，否则会切碎句子。
    """
    sep = "\n\n" if "\n\n" in text else "\n"
    atoms: list[tuple[int, int]] = []
    pos = 0
    for block in text.split(sep):
        if not block.strip():
            pos += len(block) + len(sep)
            continue
        b_start = text.index(block, pos)
        b_end = b_start + len(block)
        pos = b_end + len(sep)
        if b_end - b_start <= hard_max:
            atoms.append((b_start, b_end))
            continue
        # 单段超长：按句末标点装填
        cur = b_start
        for m in re.finditer(rf"[^{_SENT_MARK}]*[{_SENT_MARK}]+|[^{_SENT_MARK}]+$", block):
            s_end = b_start + m.end()
            if s_end - cur > hard_max and cur < b_start + m.start():
                atoms.append((cur, b_start + m.start()))
                cur = b_start + m.start()
            if s_end - cur >= hard_max:          # 单句本身就超长，硬切
                atoms.append((cur, s_end))
                cur = s_end
        if cur < b_end:
            atoms.append((cur, b_end))
    return atoms or [(0, len(text))]


def split_semantic(text: str, target: int = 700, hard_max: int = 1100) -> list[tuple[int, int]]:
    """按语义装填到 target 附近，任何块不超过 hard_max。"""
    atoms = _atoms(text, hard_max)
    chunks, cur_start, cur_end = [], atoms[0][0], atoms[0][1]
    for start, end in atoms[1:]:
        if end - cur_start <= int(target * 1.35):
            cur_end = end
        else:
            chunks.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    chunks.append((cur_start, cur_end))
    return chunks


# ------------------------------------------------------------------ 提炼（规则版）
CATEGORY_RULES = [
    ("decision", ("决定", "定了", "定在", "改口", "采用", "确定", "敲定", "继续有效")),
    ("preference", ("喜欢", "倾向", "偏好", "更愿意", "想用", "不要太", "不用讨论")),
    ("task", ("必须", "需要", "负责", "列成", "写进", "启动", "准备")),
]
_SENT = re.compile(r"[^。！？；\n]+[。！？；]?")
_HEADING = re.compile(r"^([一二三四五六七八九十]+、.+)$")


def find_topic(text: str, pos: int) -> str:
    """取该位置之前最近的一行小标题，作为条目的 topic。"""
    topic = ""
    for line in text[:pos].split("\n"):
        m = _HEADING.match(line.strip())
        if m:
            topic = m.group(1)
    return topic


def _clip(s: str, n: int = 120) -> str:
    """按句末标点截到 n 字以内，避免把句子切断。"""
    if len(s) <= n:
        return s
    head = s[:n]
    for p in "。！？；":
        i = head.rfind(p)
        if i >= n * 0.5:
            return head[:i + 1]
    return head + "…"


CAUSE = re.compile(r"(?:原因(?:是)?|理由(?:是)?|因为|由于|出于)")
RESULT = re.compile(r"(?:所以|因此|于是|故而)")
_TAIL = re.compile(r"[。；！？].*$", re.S)


def decompose(para: str) -> tuple[str, str]:
    """把一段话拆成「结论」与「依据」。

    记忆的价值不在"定了什么"，而在"凭什么这么定"。截断式摘要最容易把
    后半段的理由切掉，所以这里显式拆开，再按"结论——因为依据"重排。
    """
    m = CAUSE.search(para)
    if m:
        concl = para[:m.start()].strip(" ，。；、：:—-")
        reason = _TAIL.sub("", para[m.end():].strip(" ，。；、：:—-"))
        if concl and reason:
            return concl, reason

    # 反过来写的：「…冷萃要提前泡，所以必须前一晚准备」
    m = RESULT.search(para)
    if m:
        reason = para[:m.start()].strip(" ，。；、：:—-")
        concl = _TAIL.sub("", para[m.end():].strip(" ，。；、：:—-"))
        if concl and reason:
            return concl, reason
    return "", ""


REASON_START = re.compile(r"^\s*(?:原因|因为|考虑到|理由|背景|动机|之所以)")


def extract(text: str, chunk: str, *, chunk_start: int = 0,
            max_items: int = 20) -> list[dict]:
    """规则提炼——LLM 关闭时的降级路径（方案 6.6.5）。

    以**段落**为单位（拆句会丢指代），并把段落拆成「结论 + 依据」：
    结论控制在 50 字内，依据控制在 60 字内，凑成一句可复述的话。
    """
    scored = []
    for m in re.finditer(r"[^\n]+", chunk):
        raw = m.group(0)
        para = raw.strip()
        if len(para) < 12:
            continue
        hits, cat = 0, "knowledge"
        for name, kws in CATEGORY_RULES:
            if any(k in para for k in kws):
                cat, hits = name, hits + 3
                break
        hits += sum(1 for k in ("我们", "所以", "因为", "但是", "如果") if k in para)
        hits += min(len(para), 140) / 140.0
        if re.search(r"\d", para):
            hits += 1.0
        scored.append((hits, cat, para, chunk_start + m.start(), len(raw)))

    scored.sort(key=lambda x: -x[0])
    items, seen = [], set()
    for _, cat, para, abspos, rawlen in scored:
        concl, reason = decompose(para)
        if concl and reason:
            summary = f"{_clip(concl, 50)}——因为{_clip(reason, 60)}"
        else:
            summary = _clip(para, 110)
        key = content_hash(summary, 8)
        if key in seen:
            continue
        seen.add(key)
        topic = find_topic(text, abspos)
        words = [w.strip("，。、：；（）") for w in re.split(r"[，。、：；（）]", para) if len(w) >= 2]
        kws = ([topic] if topic else []) + words[:2]
        items.append({
            "category": cat,
            "l1_summary": summary,
            "score": round(hits, 2),
            "keywords": " ".join(k for k in kws if k),
            "offset": abspos,
            "length": rawlen,
            "topic": topic,
            "importance": {"decision": 0.8, "preference": 0.7, "task": 0.6}.get(cat, 0.5),
            "confidence": "medium",
        })
        if len(items) >= max_items:
            break

    # 每条都补「为什么」：取同一份材料里紧随其后的原因段
    paras = [(m.start(), m.group(0).strip()) for m in re.finditer(r"[^\n]+", chunk)]
    for it in items:
        if "——因为" in it["l1_summary"]:
            it["reason"] = ""                     # 理由已经在摘要里
            continue
        rel = it.get("offset", 0) - chunk_start
        cand = [(pos, txt) for pos, txt in paras if pos >= rel and REASON_START.match(txt)]
        it["reason"] = _clip(cand[0][1], 90) if cand else ""
    return items


def make_topic(summary: str) -> str:
    return summary[:18].rstrip("，。、；：…")


# ------------------------------------------------------------------ 写入
def _kw_with_title(keywords: str, title: str) -> str:
    """关键词保持原样。

    曾把来源标题并进来，好让「选址」这类词直接命中——但实测内容检索
    R@1 从 100% 掉到 35%：标题词污染了关键词列，整篇文档的条目互相顶。
    改为：材料名查询走 title_rows 兜底 + 标题加分。
    """
    return keywords


def insert_memory(conn, *, user_id, summary, category, doc_id=None, offset=None,
                  length=None, chunk_index=None, importance=0.5,
                  confidence="medium", group_id=None,
                  version_no=None, predecessor_id=None, keywords="",
                  context: str = "", reason: str = "", created_at: str | None = None,
                  extract_state: str = "provisional") -> str:
    summary = summary.strip()
    tokenized = tokenize_for_index(summary)
    kw_tokens = tokenize_for_index(keywords) if keywords else ""
    with tx(conn):
        if group_id is None:
            group_id = new_id("g")
            entry_id = new_id("mem")
            conn.execute(
                "INSERT INTO memory_groups(group_id,root_id,user_id,topic,current_version_no,created_at)"
                " VALUES (?,?,?,?,1,?)", (group_id, entry_id, user_id, make_topic(summary), now()))
            version, predecessor, root = 1, None, entry_id
        else:
            root = conn.execute("SELECT root_id FROM memory_groups WHERE group_id=?",
                                (group_id,)).fetchone()[0]
            entry_id = new_id("mem")
            if version_no is not None:
                version, predecessor = version_no, predecessor_id
            else:
                row = conn.execute(
                    "SELECT entry_id, version_no FROM memory_entries "
                    "WHERE memory_group_id=? AND status='active'", (group_id,)).fetchone()
                version = (row["version_no"] + 1) if row else 1
                predecessor = row["entry_id"] if row else None
        conn.execute(
            "INSERT INTO memory_entries(entry_id,user_id,memory_group_id,root_id,version_no,"
            "predecessor_id,category,l1_summary,tokenized,kw_tokens,keywords,context,"
            "reason,doc_id,l0_offset,l0_length,chunk_index,confidence,importance,"
            "extract_state,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?)",
            (entry_id, user_id, group_id, root, version, predecessor, category, summary,
             tokenized, kw_tokens, keywords, context, reason, doc_id, offset, length,
             chunk_index, confidence, importance, extract_state, created_at or now()))
        conn.execute("UPDATE memory_groups SET current_version_no=? WHERE group_id=?",
                     (version, group_id))
        return entry_id


RULE_MIN_SCORE = 2.0      # 低于它就当"没有可记的信号"
RULE_MAX_ITEMS = 60       # 单份材料的上限，防止长文灌爆


def select_items(items: list[dict], n_chars: int) -> list[dict]:
    """精确优先：先按绝对阈值筛，再套文档预算；全被筛掉时兜底保留少量。"""
    if not items:
        return []
    # 预算只是防爆上限：短文档给足（20），长文档封顶 60。筛人靠阈值，不靠预算
    budget = max(20, min(RULE_MAX_ITEMS, n_chars // 100))
    strong = [x for x in items if x.get("score", 0) >= RULE_MIN_SCORE]
    if strong:
        strong.sort(key=lambda x: -x["score"])
        keep = {id(x) for x in strong[:budget]}
        return [x for x in items if id(x) in keep]
    # 整份都没有信号（小说、说明书）：与其记 175 条垃圾，不如留几条并标明低置信
    fallback = sorted(items, key=lambda x: -x["score"])[:max(3, min(8, budget))]
    for x in fallback:
        x["confidence"] = "low"
    keep = {id(x) for x in fallback}
    return [x for x in items if id(x) in keep]


def ingest(conn, text: str, *, user_id="owner", title="", source="import",
           doc_id: str | None = None, extractor=None, judge_fn=None,
           judge_fns: list | None = None, project: str = "") -> dict:
    if doc_id is None:
        doc_id = put_document(conn, text, user_id=user_id, title=title, source=source)
    elif not title:
        row = conn.execute("SELECT title FROM memory_documents WHERE doc_id=?",
                           (doc_id,)).fetchone()
        title = (row["title"] if row else "") or "未命名材料"
    chunks = split_semantic(text)
    items_all = []
    seen_topic: dict[str, list[dict]] = {}
    # 写入只用本地规则：快、确定、不依赖外部服务；LLM 精修走 refine()
    produce = extract
    gathered: list[tuple[int, dict]] = []
    for idx, (start, end) in enumerate(chunks):
        for item in produce(text, text[start:end], chunk_start=start):
            gathered.append((idx, item))

    if extractor is None:                       # 只有规则版需要筛；LLM 输出本就稀疏
        kept = select_items([it for _, it in gathered], len(text))
        keep_ids = {id(x) for x in kept}
        gathered = [(i, it) for i, it in gathered if id(it) in keep_ids]

    # 项目层：有 project 就挂到项目下；没有就保持"材料即根"
    proj = (project or "").strip()
    if proj:
        parent = ensure_concept(conn, proj, None, 0)
        level = 1
    else:
        parent, level = None, 0

    for idx, item in sorted(gathered, key=lambda p: p[1]["offset"]):
            # 前因：同一话题里、比它早的那几段。链首（没有上一版）尤其需要
            prior = [x for x in seen_topic.get(item["topic"], [])
                     if x["offset"] < item["offset"]]
            ctx = (item.get("context") or "").strip() or \
                " → ".join(_clip(p["l1_summary"], 36) for p in prior[-2:])
            seen_topic.setdefault(item["topic"], []).append(item)
            sec = topic_key(item["topic"] or "").removeprefix("回到").strip()
            doc_concept = ensure_concept(conn, (title_words(title) or "未命名材料"), parent, level)
            hub = doc_concept
            eid = insert_memory(conn, user_id=user_id, summary=item["l1_summary"],
                                reason=item.get("reason", ""),
                                category=item["category"], doc_id=doc_id,
                                offset=item["offset"], length=item["length"],
                                chunk_index=idx,
                                importance=item["importance"],
                                confidence=item["confidence"],
                                keywords=_kw_with_title(item.get("keywords", ""), title),
                                context=ctx)
            link_concept(conn, eid, hub)
            if sec:
                sec_id = ensure_concept(conn, sec, hub, level + 1)
                link_concept(conn, eid, sec_id)
            items_all.append({**item, "entry_id": eid, "chunk_index": idx})
    conflicts = check_conflicts(conn, judge_fn=judge_fn, judge_fns=judge_fns, doc_id=doc_id)
    links = link_complements(conn, doc_id)
    conn.execute("UPDATE memory_documents SET entry_count=? WHERE doc_id=?",
                 (len(items_all), doc_id))
    doc = conn.execute("SELECT char_count, raw_size, compressed_size FROM memory_documents"
                       " WHERE doc_id=?", (doc_id,)).fetchone()
    log_event("ingest", "document ingested", doc=doc_id, title=title or "-",
              chunks=len(chunks), entries=len(items_all))
    return {"doc_id": doc_id, "chunks": len(chunks), "entries": items_all,
            "conflicts": conflicts, "complements": links,
            "chars": doc["char_count"], "raw_size": doc["raw_size"],
            "compressed_size": doc["compressed_size"]}


# ------------------------------------------------------------------ 检索
HALFLIFE = {"decision": 365, "knowledge": 180, "preference": 365, "task": 30}
W_TITLE = 0.5    # 查询词全部命中来源标题时的加分（标定：R@1 57%→86%）
W_BODY = 1.0     # bm25 正文列权重
W_KW = 0.35      # bm25 关键词列权重（含来源标题）
W_REL, W_REC, W_WEIGHT = 0.60, 0.25, 0.15


def recency(created_at: str, category: str) -> float:
    """S_rec = 0.5 ^ (age_days / half_life)，与方案 7.2 同口径。"""
    try:
        t = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.5
    age_days = max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 86400)
    return 0.5 ** (age_days / HALFLIFE.get(category, 180))


def _apply_title_bonus(conn, hits: list[dict], query: str) -> None:
    """查询词全部出现在来源标题里 → 加分。按材料名找东西时这是最强信号。"""
    toks = [t for t in tokenize(query) if t]
    if not toks:
        return
    ids = [h["entry_id"] for h in hits]
    marks = ",".join("?" * len(ids))
    titles = {}
    for r in conn.execute(
            f"SELECT e.entry_id, d.title FROM memory_entries e "
            f"LEFT JOIN memory_documents d ON d.doc_id=e.doc_id "
            f"WHERE e.entry_id IN ({marks})", ids):
        titles[r["entry_id"]] = title_words(r["title"] or "")
    q_norm = "".join(toks)
    for h in hits:
        tw = titles.get(h["entry_id"], "")
        # 只有查询本身就是材料名（或它的前缀）才加分；否则内容查询会被整篇文档顶掉
        matched = bool(tw) and (tw == q_norm or (len(q_norm) >= 3 and tw.startswith(q_norm)))
        if matched:
            h["score"] = round(h["score"] + W_TITLE, 3)
            h["title_hit"] = True


def title_rows(conn, query: str, statuses: tuple[str, ...]) -> list:
    """FTS 无命中时的兜底：按来源文件名、关键词、摘要做字面匹配。

    为什么需要：全文索引只覆盖摘要，而用户常按"这是哪份材料"来找
    （搜「选址」，摘要写的是"大学城""创业园区"，一条都不含"选址"）。

    排序：命中词越多越靠前（rank 取负值，越小越好，与 bm25 的方向一致）。
    """
    toks = [t for t in tokenize(query) if len(t) >= 1]
    if not toks:
        return []
    marks = ",".join("?" * len(statuses))
    score_expr = " + ".join(["(d.title LIKE ?) + (e.keywords LIKE ?)"] * len(toks))
    where_expr = " OR ".join(["(d.title LIKE ? OR e.keywords LIKE ?)"] * len(toks))
    likes = []
    for t in toks:
        likes += [f"%{t}%", f"%{t}%"]
    sql = (f"SELECT e.*, -(0.0 + {score_expr}) AS rank FROM memory_entries e "
           f"LEFT JOIN memory_documents d ON d.doc_id = e.doc_id "
           f"WHERE e.status IN ({marks}) AND ({where_expr}) "
           f"ORDER BY rank LIMIT 50")
    return conn.execute(sql, likes + list(statuses) + likes).fetchall()


def search(conn, query: str, *, mode: str = "active", top_k: int = 5) -> list[dict]:
    # hybrid：一次给全（现行 + 历史），同组只留一条且优先现行——用户不必先判断"这条还有效吗"
    if mode == "hybrid":
        act = search(conn, query, mode="active", top_k=top_k * 2)
        his = search(conn, query, mode="history", top_k=top_k * 2)
        # s_rel 是在各自集合内归一化的，score 不能跨集合直接比。
        # 这里把每个集合的分数压到 0~1 再合并，否则"历史集合只有两条"会让旧版本虚高。
        both = act + his
        top = max((x["score"] for x in both), default=0.0) or 1.0
        for x in both:
            x["score_norm"] = round(x["score"] / top, 4)

        by_group: dict[str, list[dict]] = {}
        for it in both:
            by_group.setdefault(it.get("group") or it["entry_id"], []).append(it)
        picked = []
        for members in by_group.values():
            # 同组只出一条：优先现行，其次归一化分最高的
            members.sort(key=lambda x: (x["status"] == "active", x["score_norm"]), reverse=True)
            picked.append(members[0])
        picked.sort(key=lambda x: x["score_norm"], reverse=True)
        return picked[:top_k]

    if mode == "history":
        fts, statuses = "memory_fts_history", ("superseded", "archived")
    else:
        fts, statuses = "memory_fts_active", ("active",)

    def fts_rows(expr: str):
        return conn.execute(
            f"""SELECT e.*, bm25({fts}, 0.0, {W_BODY}, {W_KW}) AS rank
                  FROM {fts} f JOIN memory_entries e ON e.row_id = f.rowid
                 WHERE {fts} MATCH ?
                 ORDER BY rank LIMIT 50""", (expr,)).fetchall()

    rows = []
    expr = build_match(query, "and")
    if expr:
        rows = fts_rows(expr)
        if len(rows) < 3:                  # 太少了就放宽成 OR
            rows = fts_rows(build_match(query, "or"))
    # 标题/关键词字面命中总是并进来：FTS 有结果时也要，否则"那是在哪份材料里"这类查询会被挤掉
    seen = {r["entry_id"] for r in rows}
    for r in title_rows(conn, query, statuses):
        if r["entry_id"] not in seen:
            rows.append(r)
            seen.add(r["entry_id"])
    if not rows:
        return []

    ranks = [r["rank"] for r in rows]
    best, worst = min(ranks), max(ranks)
    span = (worst - best) or 1.0
    flat = worst == best
    out = []
    for r in rows:
        s_rel = 1.0 if flat else (worst - r["rank"]) / span
        s_rec = recency(r["created_at"], r["category"])
        out.append({"entry_id": r["entry_id"], "l1_summary": r["l1_summary"],
                    "category": r["category"], "status": r["status"],
                    "version_no": r["version_no"], "group": r["memory_group_id"],
                    "s_rel": round(s_rel, 3),
                    "s_rec": round(s_rec, 3), "weight": r["weight"],
                    "score": round(W_REL * s_rel + W_REC * s_rec + W_WEIGHT * r["weight"], 3),
                    "created_at": r["created_at"],
                    "bm25": round(r["rank"], 3)})
    if out and W_TITLE:
        _apply_title_bonus(conn, out, query)
    out.sort(key=lambda x: -x["score"])
    out = out[:top_k]
    if out:                                # 有相关记忆的，卡片上给个提示（一次查完）
        ids = [x["entry_id"] for x in out]
        marks = ",".join("?" * len(ids))
        counts: dict[str, int] = {}
        for r in conn.execute(
                f"SELECT entry_id, count(*) c FROM ("
                f"  SELECT from_entry AS entry_id FROM memory_relations WHERE from_entry IN ({marks})"
                f"  UNION ALL"
                f"  SELECT to_entry   AS entry_id FROM memory_relations WHERE to_entry   IN ({marks})"
                f") GROUP BY entry_id", ids + ids):
            counts[r["entry_id"]] = r["c"]
        for item in out:
            item["rel_count"] = counts.get(item["entry_id"], 0)
    return out


# ------------------------------------------------------------------ 版本链
def supersede(conn, entry_id: str, new_summary: str) -> dict:
    old = conn.execute("SELECT * FROM memory_entries WHERE entry_id=?", (entry_id,)).fetchone()
    if old is None:
        raise KeyError(entry_id)
    if old["status"] != "active":
        raise RuntimeError("NOT_ACTIVE")
    with tx(conn):
        cur = conn.execute(
            "UPDATE memory_entries SET status='superseded' "
            "WHERE entry_id=? AND version_no=? AND status='active'",
            (entry_id, old["version_no"]))
        if cur.rowcount != 1:
            raise RuntimeError("ESTALE")
        new_id_ = insert_memory(conn, user_id=old["user_id"], summary=new_summary,
                                category=old["category"], doc_id=old["doc_id"],
                                offset=old["l0_offset"], length=old["l0_length"],
                                chunk_index=old["chunk_index"],
                                importance=old["importance"],
                                group_id=old["memory_group_id"],
                                version_no=old["version_no"] + 1,
                                predecessor_id=entry_id)
        conn.execute("UPDATE memory_entries SET superseded_by=? WHERE entry_id=?",
                     (new_id_, entry_id))
    return {"old": entry_id, "new": new_id_, "group": old["memory_group_id"]}


def chain(conn, group_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT entry_id, version_no, status, l1_summary, context, reason, superseded_by, "
        "created_at FROM memory_entries WHERE memory_group_id=? ORDER BY version_no",
        (group_id,))]


# 这句话在干什么：改动 / 拍板 / 罗列 / 备注。配对时只有前两种能当前任。
ACT_CHANGE = ("改口", "改成", "改为", "不再", "换成", "换到", "推翻", "取消",
              "放弃", "替代", "调到", "搬到", "重定", "定下来", "敲定", "改为")
DECISION_RE = re.compile(r"(决定|敲定|最终定|定[了在为用下成]|设为|采用|确定|选了)")
ACT_SURVEY = ("讨论过", "候选", "考虑过", "比较了", "方案有", "几个方案")


def speech_act(text: str) -> str:
    if CHANGE_RE.search(text):
        return "change"
    if DECISION_RE.search(text):
        return "decision"
    if any(k in text for k in ACT_SURVEY):
        return "survey"
    return "note"


TOPIC_NOISE = re.compile(r"^[一二三四五六七八九十]+、|^回到|这件事$|这个问题$|这档子事$")
# 改动语义用正则表达："改到/改换/改用" 这类词穷举不完，之前就因此漏判过
CHANGE_RE = re.compile(r"改(?:成|为|到|换|用|口)|换成|换到|推翻|取消|放弃|替代|搬到|调到|重定|定下来|不再")


_DOC_PREFIX = re.compile(r"^[\d\s_\-\.、（）()]+")


def title_words(title: str) -> str:
    """文件名 → 可索引的词。`02_选址改口.md` → `选址改口`。"""
    if not title:
        return ""
    t = Path(title).stem if "." in title else title
    return _DOC_PREFIX.sub("", t).strip()


def _doc_topic(title: str | None) -> str:
    """文档标题 → 话题。`02_选址改口.md` → `选址改口`。"""
    if not title:
        return ""
    t = Path(title).stem if "." in title else title
    t = _DOC_PREFIX.sub("", t).strip()
    return topic_key(t[:8])


def topic_key(topic: str) -> str:
    return TOPIC_NOISE.sub("", (topic or "").strip()).strip()


def _tokens(text: str) -> set[str]:
    return set(tokenize(text))


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def judge(new_sum: str, new_kw: str, old_sum: str, old_kw: str) -> tuple[str, float, str]:
    """规则判定——LLM 关闭时的降级路径（方案 6.9.2）。

    没有语义模型，就用两条可判据：① 是否同一话题（来自小标题）；
    ② 新句里有没有"变更标记"。这两条合起来能抓住"改口"这类覆盖。
    """
    ov = _overlap(_tokens(new_sum), _tokens(old_sum))
    nt, ot = topic_key(new_kw.split()[0] if new_kw else ""), topic_key(old_kw.split()[0] if old_kw else "")
    same_topic = bool(nt) and bool(ot) and (nt in ot or ot in nt)
    markers = [x.group(0) for x in CHANGE_RE.finditer(new_sum)
               if x.group(0) not in old_sum]

    if ov >= 0.85:
        return ("duplicate", 0.9, f"措辞几乎相同（重合度 {ov:.2f}）")
    shared = len(_tokens(new_sum) & _tokens(old_sum))
    if same_topic and markers and (ov >= 0.08 or shared >= 2):
        return ("override", 0.85,
                f"同属「{nt}」，出现变更标记（{ '、'.join(markers[:2]) }），共享 {shared} 个实词")
    if same_topic and markers:
        return ("complement", 0.5,
                f"同属「{nt}」且提到变更，但没有字面锚点（{ov:.2f}），不足以判定覆盖")
    if same_topic:
        return ("complement", 0.6, f"同属「{nt}」，补充细节")
    if ov >= 0.5:
        return ("complement", 0.5, f"字面重合度较高（{ov:.2f}）")
    return ("unrelated", 0.0, "")


SEVERITY = {"unrelated": 0, "complement": 1, "duplicate": 2, "override": 3}


def merge_verdicts(results: list[tuple[str, float, str]]) -> tuple[str, float, str]:
    """并集：取最"重"的关系。两个判定器任一认为被覆盖，就按覆盖处理。

    理由：漏判的代价（旧结论继续生效）远大于误判的代价（多点一次裁决）。
    """
    if not results:
        return "unrelated", 0.0, ""
    rel, conf, reason = max(results, key=lambda x: (SEVERITY[x[0]], x[1]))
    if len(results) > 1:
        others = [f"{r} {c:.2f}" for r, c, _ in results if not (r == rel and abs(c - conf) < 1e-9)]
        if others and any(SEVERITY[r] != SEVERITY[rel] for r, _, _ in results):
            reason = f"{reason}（另一判定器：{'、'.join(others)}）"
    return rel, conf, reason


def check_conflicts(conn, *, threshold: float = 0.8, judge_fn=None,
                    judge_fns: list | None = None,
                    min_score: float = 0.04, doc_id: str | None = None) -> list[dict]:
    """对同批条目两两判定；高置信的"覆盖/重复"不自动执行，只挂起。

    doc_id 给定时**只把这份材料的条目当"新"**——否则每灌一份新材料都会把全表
    重扫一遍，已裁决过的旧条目会被重新配对、重新挂起（实测过）。
    """
    rows = conn.execute(
        "SELECT e.entry_id, e.l1_summary, e.keywords, e.category, e.created_at, e.doc_id, "
        "e.status, e.memory_group_id, e.row_id, d.title AS doc_title "
        "FROM memory_entries e LEFT JOIN memory_documents d ON d.doc_id = e.doc_id "
        "WHERE e.status IN ('active','pending_merge') ORDER BY e.row_id").fetchall()
    # b（新决定）只能是本次入库那份材料的条目；a（前任）可以是任何更早的条目
    new_ids = ({r["entry_id"] for r in rows if r["doc_id"] == doc_id}
               if doc_id else {r["entry_id"] for r in rows})
    # 组内现行版本，循环外算一次；之前每行都重算一遍，是 O(n²)
    heads = {r["entry_id"] for r in rows if r["status"] == "active"}
    found = []
    with tx(conn):
        for i, b in enumerate(rows):
            if doc_id and b["entry_id"] not in new_ids:
                continue                       # 老条目不是"新决定"，不参与判定
            # 只和"比它早、且最相似"的那一条比：候选召回本就该取 top-1 再判定
            act_b = speech_act(b["l1_summary"])
            if act_b not in ("change", "decision"):
                continue                        # 罗列/备注不主动去改别人
            cands: list[tuple[float, float, dict]] = []
            for a in rows[:i]:
                if a["doc_id"] == b["doc_id"] and a["row_id"] >= b["row_id"]:
                    continue                        # 同批里更晚的不算前任
                # 候选可以是任何"现行"条目——价格表/营业时间这类陈述句也算政策，
                # 是否真被覆盖交给下面的 judge 判（同话题 + 变更标记 + 字面锚点）
                if a["status"] == "superseded":
                    continue
                ov = _overlap(_tokens(b["l1_summary"]), _tokens(a["l1_summary"]))
                nt, ot = _doc_topic(b["doc_title"]), _doc_topic(a["doc_title"])
                same = 1.0 if (nt and ot and (nt == ot or nt in ot or ot in nt)) else 0.0
                score = 0.7 * ov + 0.3 * same
                if a["entry_id"] in heads:
                    score += 0.06               # 优先挂在组内现行版本上，别挂在老尸首上
                cands.append((score, same, a))
            fns = judge_fns or ([judge_fn] if judge_fn else [judge])
            # 排序：同话题 > 是不是"决定" > 字面分。
            # 少了中间那档，改口会挂到"备选是…"这类陈述句上，真正的旧决定依然是 active。
            cands.sort(key=lambda x: (-x[1],
                                      -int(speech_act(x[2]["l1_summary"]) in ("decision", "change")),
                                      -x[0]))

            cands = [c for c in cands[:5] if c[0] >= min_score]
            if not cands:
                continue                        # 召回分太低，不值得动用贵模型
            for best_score, _, a in cands:
                # 注意：这里必须用「当前候选」的话题重算，
                # 不能沿用上面打分循环遗留的 nt/ot（那是最后一条候选的）
                _nt, _ot = _doc_topic(b["doc_title"]), _doc_topic(a["doc_title"])
                b_kw = f"{_nt} {b['keywords']}" if _nt else b["keywords"]
                a_kw = f"{_ot} {a['keywords']}" if _ot else a["keywords"]
                goods = [fn(b["l1_summary"], b_kw, a["l1_summary"], a_kw) for fn in fns]
                rel, conf, reason = merge_verdicts(goods)

                if rel not in ("override", "duplicate") or conf < threshold:
                    continue                        # 这条候选不像，换下一条
                exists = conn.execute(
                    "SELECT 1 FROM memory_conflicts WHERE "
                    "(old_entry_id=? AND new_entry_id=?) OR (old_entry_id=? AND new_entry_id=?)",
                    (a["entry_id"], b["entry_id"], b["entry_id"], a["entry_id"])).fetchone()
                if exists:
                    continue
                log_event("conflict", "conflict detected", old=a["entry_id"],
                          new=b["entry_id"], relation=rel, confidence=round(conf, 2))
                cid = new_id("c")
                conn.execute(
                    "INSERT INTO memory_conflicts(conflict_id,old_entry_id,new_entry_id,"
                    "relation,similarity,confidence,reason,suggestion,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (cid, a["entry_id"], b["entry_id"], rel, round(conf, 3), conf, reason,
                     "supersede", now()))
                conn.execute("UPDATE memory_entries SET status='pending_merge' "
                             "WHERE entry_id=? AND status='active'", (b["entry_id"],))
                found.append({"conflict_id": cid, "relation": rel, "confidence": conf,
                              "reason": reason,
                              "old": a["l1_summary"], "new": b["l1_summary"],
                              "old_id": a["entry_id"], "new_id": b["entry_id"]})
                break                               # 一条新条目最多挂一处冲突
    return found


def link_complements(conn, doc_id: str, *, max_links: int = 3) -> list[dict]:
    """把新条目挂到"同话题、但只是补充"的旧条目上——不作废、不建版本。

    与冲突的区别只在一点：新条目没有变更标记。所以它不改写任何东西，
    只在两条之间留一条关系，供"看这条时顺便看到相关的那条"。
    """
    new_rows = conn.execute(
        "SELECT entry_id, l1_summary, keywords FROM memory_entries "
        "WHERE doc_id=? AND status IN ('active','pending_merge')", (doc_id,)).fetchall()
    others = conn.execute(
        "SELECT entry_id, l1_summary, keywords FROM memory_entries "
        "WHERE doc_id<>? AND status IN ('active','pending_merge')", (doc_id,)).fetchall()
    tok_cache = {r["entry_id"]: _tokens(r["l1_summary"]) for r in others}
    out = []
    with tx(conn):
        for b in new_rows:
            best, best_score, best_reason = None, 0.0, ""
            b_tok = _tokens(b["l1_summary"])
            for a in others:
                rel, conf, reason = judge(b["l1_summary"], b["keywords"],
                                          a["l1_summary"], a["keywords"])
                if rel != "complement":
                    continue
                shared = len(b_tok & tok_cache[a["entry_id"]])
                if shared < 1:                     # 没有任何共同实词，不敢连
                    continue
                score = conf + 0.05 * shared
                if score > best_score:
                    best, best_score, best_reason = a, score, reason
            if best is None:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO memory_relations(relation_id,from_entry,to_entry,"
                "relation,confidence,reason,created_at) VALUES (?,?,?,?,?,?,?)",
                (new_id("r"), b["entry_id"], best["entry_id"], "complement",
                 round(min(best_score, 0.99), 2), best_reason, now()))
            out.append({"new": b["entry_id"], "new_summary": b["l1_summary"],
                        "old": best["entry_id"], "old_summary": best["l1_summary"],
                        "confidence": round(min(best_score, 0.99), 2),
                        "reason": best_reason})
            if len(out) >= max_links:
                break
    return out


def relations_of(conn, entry_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM memory_relations WHERE from_entry=? OR to_entry=? "
        "ORDER BY created_at", (entry_id, entry_id))]


def list_conflicts(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM memory_conflicts WHERE state='open' ORDER BY created_at")]


def resolve_conflict(conn, conflict_id: str, resolution: str) -> dict:
    """四选一：supersede / keep_both / ignore。"""
    c = conn.execute("SELECT * FROM memory_conflicts WHERE conflict_id=?",
                     (conflict_id,)).fetchone()
    if c is None:
        raise KeyError(conflict_id)
    old = conn.execute("SELECT * FROM memory_entries WHERE entry_id=?",
                       (c["old_entry_id"],)).fetchone()
    new = conn.execute("SELECT * FROM memory_entries WHERE entry_id=?",
                       (c["new_entry_id"],)).fetchone()

    with tx(conn):
        if resolution == "supersede":
            # 老条目可能已经被别的裁决取代过，所以要以组内当前 active 为基准
            head = old
            if old["status"] != "active":
                row = conn.execute(
                    "SELECT * FROM memory_entries WHERE memory_group_id=? AND status='active'",
                    (old["memory_group_id"],)).fetchone()
                head = row or old
            ver = conn.execute(
                "SELECT coalesce(max(version_no), 0) + 1 FROM memory_entries "
                "WHERE memory_group_id=?", (head["memory_group_id"],)).fetchone()[0]
            conn.execute(
                "UPDATE memory_entries SET memory_group_id=?, root_id=?, version_no=?, "
                "predecessor_id=?, status='active' WHERE entry_id=?",
                (head["memory_group_id"], head["root_id"], ver,
                 head["entry_id"], new["entry_id"]))
            conn.execute("UPDATE memory_entries SET status='superseded', superseded_by=? "
                         "WHERE entry_id=?", (new["entry_id"], head["entry_id"]))
            conn.execute("UPDATE memory_groups SET current_version_no=? WHERE group_id=?",
                         (ver, head["memory_group_id"]))
            left = conn.execute("SELECT count(*) FROM memory_entries WHERE memory_group_id=?",
                                (new["memory_group_id"],)).fetchone()[0]
            if left == 0:
                conn.execute("DELETE FROM memory_groups WHERE group_id=?",
                             (new["memory_group_id"],))
            state = "resolved"
        else:
            conn.execute("UPDATE memory_entries SET status='active' WHERE entry_id=?",
                         (new["entry_id"],))
            state = "resolved" if resolution == "keep_both" else "ignored"

        conn.execute("UPDATE memory_conflicts SET state=?, resolution=? WHERE conflict_id=?",
                     (state, resolution, conflict_id))
    audit(conn, "owner", "resolve", new["entry_id"], conflict=conflict_id,
          resolution=resolution)
    log_event("conflict", "conflict resolved", conflict=conflict_id, resolution=resolution)
    return {"conflict_id": conflict_id, "resolution": resolution, "state": state}


def entry_origin(conn, entry_id: str) -> dict:
    """这条记忆从哪来：哪份材料、属于哪个项目。"""
    row = conn.execute(
        "SELECT e.doc_id, d.title FROM memory_entries e "
        "LEFT JOIN memory_documents d ON d.doc_id = e.doc_id WHERE e.entry_id=?",
        (entry_id,)).fetchone()
    out = {"doc_title": "", "doc_id": "", "project": ""}
    if row:
        out["doc_id"] = row["doc_id"] or ""
        out["doc_title"] = row["title"] or ""
    # 项目 = 该条目挂的概念里，level 最小的那个根
    cid = conn.execute("SELECT concept_id FROM memory_entry_concepts WHERE entry_id=? "
                       "LIMIT 1", (entry_id,)).fetchone()
    if cid:
        cur, seen = cid["concept_id"], set()
        best = None
        while cur and cur not in seen:
            seen.add(cur)
            r = conn.execute("SELECT concept_id, name, parent_id, level FROM memory_concepts "
                             "WHERE concept_id=?", (cur,)).fetchone()
            if r is None:
                break
            if best is None or r["level"] < best["level"]:
                best = r
            cur = r["parent_id"]
        if best:
            out["project"] = best["name"]
    return out


def list_entries(conn, *, status: str = "archived", category: str = "",
                 limit: int = 50) -> list[dict]:
    """按状态列记忆（归档视图、未精修视图都用它）。"""
    where = ["1=1"]
    args: list = []
    if status == "archived":
        where.append("status='archived'")
    elif status == "active":
        where.append("status='active'")
    elif status == "pending":
        where.append("status='pending_merge'")
    elif status == "provisional":
        where.append("extract_state='provisional' AND status IN ('active','pending_merge')")
    if category:
        where.append("category=?")
        args.append(category)
    sql = ("SELECT entry_id, l1_summary, category, status, version_no, created_at, "
           "extract_state FROM memory_entries WHERE " + " AND ".join(where) +
           " ORDER BY created_at DESC LIMIT ?")
    args.append(max(1, min(limit, 500)))
    return [dict(r) for r in conn.execute(sql, args)]


def entry_revisions(conn, entry_id: str, limit: int = 20) -> list[dict]:
    """这条记忆被改过几次（精修 / 手改 / 回滚都算）。"""
    return [dict(r) for r in conn.execute(
        "SELECT revision_id, old_summary, new_summary, reason, created_at "
        "FROM memory_revisions WHERE entry_id=? ORDER BY created_at DESC LIMIT ?",
        (entry_id, max(1, min(limit, 100))))]


def revert_summary(conn, entry_id: str, revision_id: str) -> dict:
    """把摘要回滚到某个历史版本；回滚本身也留一条痕迹。"""
    rev = conn.execute("SELECT old_summary FROM memory_revisions WHERE revision_id=? "
                       "AND entry_id=?", (revision_id, entry_id)).fetchone()
    if rev is None:
        raise KeyError("没有这条历史版本")
    target = rev["old_summary"]
    return update_summary(conn, entry_id, target, why=f"revert:{revision_id}")


def make_backup(root: Path, keep: int = 0) -> dict:
    """备份到 <数据目录>/backup/<时间戳>/，并做一致性校验。

    用 sqlite 的 backup 接口而不是复制文件：复制会拿到 WAL 中间态。
    """
    import hashlib
    import json
    import shutil
    import sqlite3
    from datetime import datetime

    root = Path(root)
    db = root / "memory.db"
    if not db.exists():
        raise FileNotFoundError("还没有数据库")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = root / "backup" / stamp
    dest.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(db)
    tgt = sqlite3.connect(dest / "memory.db")
    try:
        src.backup(tgt)
    finally:
        tgt.close()
        src.close()
    if (root / "l0").exists():
        shutil.copytree(root / "l0", dest / "l0", dirs_exist_ok=True)
    if (root / "config.toml").exists():
        shutil.copy2(root / "config.toml", dest / "config.toml")

    def counts(path):
        c = sqlite3.connect(path)
        try:
            return {k: c.execute(sql).fetchone()[0] for k, sql in (
                ("documents", "SELECT count(*) FROM memory_documents"),
                ("entries", "SELECT count(*) FROM memory_entries"),
                ("conflicts", "SELECT count(*) FROM memory_conflicts"))}
        finally:
            c.close()

    manifest = {"created_at": stamp,
                "db_sha256": hashlib.sha256((dest / "memory.db").read_bytes()).hexdigest(),
                "counts": counts(dest / "memory.db")}
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    ok = manifest["counts"] == counts(db)
    if keep:
        olds = sorted((root / "backup").iterdir(), key=lambda x: x.name)[:-keep]
        for old in olds:
            shutil.rmtree(old, ignore_errors=True)
    log_event("backup", "backup made", dest=str(dest), entries=manifest["counts"]["entries"],
              ok=ok)
    return {"dest": str(dest), "counts": manifest["counts"], "ok": ok}


def _reindex(conn, entry_id: str) -> None:
    """改了摘要/关键词之后，把两套 FTS 都同步过去。"""
    row = conn.execute("SELECT row_id, l1_summary, keywords FROM memory_entries "
                       "WHERE entry_id=?", (entry_id,)).fetchone()
    if row is None:
        return
    body = " ".join(tokenize(row["l1_summary"]))
    kw = " ".join(tokenize(row["keywords"] or ""))
    for fts in ("memory_fts_active", "memory_fts_history"):
        conn.execute(f"UPDATE {fts} SET tokenized=?, kw_tokens=? WHERE rowid=?",
                     (body, kw, row["row_id"]))
    log_event("index", "reindexed", entry=entry_id)


def update_summary(conn, entry_id: str, new_summary: str, *, why: str = "manual_edit") -> dict:
    """改一条记忆的摘要，留痕到 memory_revisions，可回滚。"""
    new_summary = new_summary.strip()
    if len(new_summary) < 6:
        raise ValueError("摘要太短")
    row = conn.execute("SELECT l1_summary FROM memory_entries WHERE entry_id=?",
                       (entry_id,)).fetchone()
    if row is None:
        raise KeyError("没有这条记忆")
    old = row["l1_summary"]
    with tx(conn):
        conn.execute("UPDATE memory_entries SET l1_summary=? WHERE entry_id=?",
                     (new_summary, entry_id))
        conn.execute("INSERT INTO memory_revisions(revision_id,entry_id,old_summary,"
                     "new_summary,reason,created_at) VALUES (?,?,?,?,?,?)",
                     (new_id("rv"), entry_id, old, new_summary, why, now()))
        _reindex(conn, entry_id)
    audit(conn, "owner", "update", entry_id, old_len=len(old), new_len=len(new_summary))
    log_event("manual", "memory edited", entry=entry_id)
    return {"entry_id": entry_id, "old": old, "new": new_summary}


def archive(conn, entry_id: str):
    with tx(conn):
        conn.execute("UPDATE memory_entries SET status='archived' WHERE entry_id=?", (entry_id,))


def ensure_concept(conn, name: str, parent: str | None = None, level: int = 0) -> str:
    row = conn.execute("SELECT concept_id FROM memory_concepts WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    cid = new_id("k")
    conn.execute("INSERT INTO memory_concepts(concept_id,name,parent_id,level,created_at)"
                 " VALUES (?,?,?,?,?)", (cid, name, parent, level, now()))
    return cid


def link_concept(conn, entry_id: str, concept_id: str):
    conn.execute("INSERT OR IGNORE INTO memory_entry_concepts(entry_id,concept_id) VALUES (?,?)",
                 (entry_id, concept_id))


def relevel(conn) -> int:
    """按 parent_id 重算 level。挂父节点之后必须调用——否则层级是旧的。"""
    rows = conn.execute("SELECT concept_id, parent_id FROM memory_concepts").fetchall()
    parent = {r["concept_id"]: r["parent_id"] for r in rows}
    level: dict[str, int] = {}

    def depth(cid: str, seen: frozenset = frozenset()) -> int:
        if cid in level:
            return level[cid]
        p = parent.get(cid)
        if p is None or p in seen:          # 根，或父链成环（防御）
            level[cid] = 0
        else:
            level[cid] = depth(p, seen | {cid}) + 1
        return level[cid]

    changed = 0
    with tx(conn):
        for cid in parent:
            lv = depth(cid)
            cur = conn.execute("SELECT level FROM memory_concepts WHERE concept_id=?",
                               (cid,)).fetchone()[0]
            if cur != lv:
                conn.execute("UPDATE memory_concepts SET level=? WHERE concept_id=?", (lv, cid))
                changed += 1
    return changed


def concept_tree(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT c.concept_id, c.name, c.parent_id, c.level,"
        " (SELECT count(DISTINCT ec.entry_id) FROM memory_entry_concepts ec"
        "   WHERE ec.concept_id = c.concept_id) AS direct,"
        " (SELECT count(*) FROM memory_concepts x WHERE x.parent_id = c.concept_id) AS children"
        " FROM memory_concepts c ORDER BY c.level, c.name").fetchall()
    return [dict(r) for r in rows]


def concept_entries(conn, name: str, *, include_children: bool = True) -> list[dict]:
    """按概念取记忆；默认把子概念的也带上（这就是"星网"的用处）。"""
    root = conn.execute("SELECT concept_id FROM memory_concepts WHERE name=?", (name,)).fetchone()
    if root is None:
        return []
    ids = [root[0]]
    if include_children:
        frontier = [root[0]]
        while frontier:
            marks = ",".join("?" * len(frontier))
            kids = [r[0] for r in conn.execute(
                f"SELECT concept_id FROM memory_concepts WHERE parent_id IN ({marks})", frontier)]
            frontier = [k for k in kids if k not in ids]
            ids.extend(frontier)
    marks = ",".join("?" * len(ids))
    return [dict(r) for r in conn.execute(
        f"SELECT DISTINCT e.entry_id, e.l1_summary, e.category, e.status, e.version_no,"
        f" e.created_at FROM memory_entries e"
        f" JOIN memory_entry_concepts ec ON ec.entry_id = e.entry_id"
        f" WHERE ec.concept_id IN ({marks}) AND e.status IN ('active','pending_merge')"
        f" ORDER BY e.created_at DESC", ids)]


def list_chains(conn, min_versions: int = 2) -> list[dict]:
    """所有发生过更迭的版本组，按组内最新时间倒序。"""
    groups = conn.execute(
        "SELECT memory_group_id, count(*) c FROM memory_entries "
        "GROUP BY memory_group_id HAVING c >= ?", (min_versions,)).fetchall()
    out = []
    for g in groups:
        nodes = chain(conn, g["memory_group_id"])
        prev = None
        for n in nodes:
            if prev is None:
                n["gap_days"] = None
            else:
                t0 = datetime.strptime(prev, "%Y-%m-%dT%H:%M:%S.%fZ")
                t1 = datetime.strptime(n["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                n["gap_days"] = round((t1 - t0).total_seconds() / 86400, 2)
            prev = n["created_at"]
        out.append({"group_id": g["memory_group_id"], "nodes": nodes})
    out.sort(key=lambda x: x["nodes"][-1]["created_at"], reverse=True)
    return out


def stats(conn) -> dict:
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    q = lambda s: conn.execute(s).fetchone()[0]
    return {
        "documents": q("SELECT count(*) FROM memory_documents"),
        "entries": q("SELECT count(*) FROM memory_entries"),
        "active": q("SELECT count(*) FROM memory_entries WHERE status='active'"),
        "archived": q("SELECT count(*) FROM memory_entries WHERE status='archived'"),
        "pending_merge": q("SELECT count(*) FROM memory_entries WHERE status='pending_merge'"),
        "superseded": q("SELECT count(*) FROM memory_entries WHERE status='superseded'"),
        "blobs": q("SELECT count(*) FROM memory_blobs"),
        "l0_bytes": q("SELECT coalesce(sum(size),0) FROM memory_blobs"),
        "l0_raw": q("SELECT coalesce(sum(raw_size),0) FROM memory_blobs"),
        "fts_active": q("SELECT count(*) FROM memory_fts_active"),
        "fts_history": q("SELECT count(*) FROM memory_fts_history"),
        "db_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
    }


def env_info() -> dict:
    return {"python": __import__("sys").version.split()[0],
            "sqlite": sqlite3.sqlite_version,
            "codec": CODEC, "tokenizer": TOKENIZER, "db": str(DB_PATH)}


# ------------------------------------------------------------------ 对话开头：主动浮现
def active_context(conn, k: int = 5) -> dict:
    """新对话开头该浮现什么。纯本地计算，不调任何外部服务。

    打分刻意简单可解释——浮现的三五条要是错的，用户会立刻不信这个系统，
    所以要能说清"为什么是这几条"。
    """
    rows = conn.execute(
        "SELECT e.entry_id, e.l1_summary, e.category, e.status, e.version_no, e.weight,"
        " e.created_at, e.pin, e.anchor, e.memory_group_id, e.keywords, e.confidence"
        " FROM memory_entries e WHERE e.status IN ('active','pending_merge')").fetchall()

    # 每组的现行版本；别的版本一律不浮现
    heads = {}
    for r in rows:
        if r["status"] == "active":
            cur = heads.get(r["memory_group_id"])
            if cur is None or r["version_no"] > cur["version_no"]:
                heads[r["memory_group_id"]] = r

    group_size = {g: c for g, c in conn.execute(
        "SELECT memory_group_id, count(*) FROM memory_entries GROUP BY memory_group_id")}

    picked = []
    for r in heads.values():
        if REASON_START.match(r["l1_summary"]):
            continue                      # 纯理由条目已作为 reason 挂在决定上，不再单独浮现
        rec = recency(r["created_at"], r["category"])
        score = 0.50 * r["weight"] + 0.30 * rec
        why = [f"权重 {r['weight']:.2f}", f"新鲜度 {rec:.2f}"]
        if r["pin"] or r["anchor"]:
            score += 0.25
            why.append("已置顶/锚定")
        versions = group_size.get(r["memory_group_id"], 1)
        age_days = (datetime.now(timezone.utc) - datetime.strptime(
            r["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)).days
        if versions > 1 and age_days > 30:
            score += 0.15
            why.append(f"改过 {versions} 版且已 {age_days} 天，可能该复查")
        if r["status"] == "pending_merge":
            score += 0.30
            why.append("有未裁决冲突")
        picked.append({**dict(r), "score": round(score, 3), "why": "；".join(why)})

    picked.sort(key=lambda x: -x["score"])

    # 去重：同一话题最多一条；与已选条目字面高度重合的也跳过。
    # 浮现出来三条同义句，比少给一条更糟——用户会立刻不信这个系统。
    diverse, seen_topic, seen_tok = [], set(), []
    for item in picked:
        topic = topic_key((item["keywords"] or "").split()[0] if item["keywords"] else "")
        if topic and topic in seen_topic:      # 同一话题只浮现一条（不是同一版本组）
            continue
        toks = _tokens(item["l1_summary"])
        if any(len(toks & t) / max(len(toks | t), 1) > 0.55 for t in seen_tok):
            continue
        diverse.append(item)
        if topic:
            seen_topic.add(topic)
        seen_tok.append(toks)
        if len(diverse) >= k * 3:
            break
    picked = diverse

    conflicts = conn.execute(
        "SELECT count(*) c FROM memory_conflicts WHERE state='open'").fetchone()["c"]
    pending = conn.execute(
        "SELECT count(*) c FROM memory_entries WHERE extract_state='provisional'").fetchone()["c"]
    return {"memories": picked[:k], "pending_conflicts": conflicts,
            "provisional": pending, "total": len(picked)}


# ------------------------------------------------------------------ 后台精修
REFINE_PROMPT = """把这条记忆改写成「结论——因为依据」的写法。

原摘要：{old}

上下文原文：
{text}

要求：
1. **不许丢事实**：原摘要里的数字、地点、理由，改写后必须都还在。
2. 只依据原文，不编造；原文不足以支撑依据时，**原样输出原摘要**。
3. 依据只留能改变判断的部分（价格、次数、成本、时间）。
4. 一句话，不超过 100 字，格式：<结论>——因为<依据>。
5. 只输出那一句，不要解释。
"""


def refine(conn, *, limit: int = 20, user_id: str = "owner") -> dict:
    """把 provisional 条目交给 LLM 精修。失败不影响已有数据（本来就已经能用了）。"""
    import api_client

    rows = conn.execute(
        "SELECT entry_id, l1_summary, doc_id, l0_offset, l0_length FROM memory_entries "
        "WHERE extract_state='provisional' AND status='active' AND doc_id IS NOT NULL "
        "AND version_no = 1"
        " AND entry_id NOT IN (SELECT from_entry FROM memory_relations"
        "                      UNION SELECT to_entry FROM memory_relations)"
        " AND entry_id NOT IN (SELECT old_entry_id FROM memory_conflicts"
        "                      UNION SELECT new_entry_id FROM memory_conflicts)"
        " ORDER BY created_at LIMIT ?", (limit,)).fetchall()

    done, failed = [], []
    for r in rows:
        try:
            span = get_span(conn, r["entry_id"], before=150, after=150)
            text = (span.get("text") or "").strip()
            if len(text) < 20:
                continue
            new = api_client.chat(
                REFINE_PROMPT.format(old=r["l1_summary"], text=text),
                max_tokens=260).strip()
            new = new.strip("“”\" \n")
            # 防退化：没有依据结构、或者比原文短太多（丢事实）就不采纳
            if "——" not in new or len(new) < 10:
                failed.append(r["entry_id"])
                continue
            if len(new) < len(r["l1_summary"]) * 0.6:
                failed.append(r["entry_id"])
                continue
            with tx(conn):
                conn.execute("UPDATE memory_entries SET l1_summary=?, tokenized=?, "
                             "extract_state='refined', refined_at=? WHERE entry_id=?",
                             (new, tokenize_for_index(new), now(), r["entry_id"]))
                conn.execute(
                    "INSERT INTO memory_revisions(revision_id,entry_id,old_summary,"
                    "new_summary,reason,created_at) VALUES (?,?,?,?,?,?)",
                    (new_id("rv"), r["entry_id"], r["l1_summary"], new, "llm_refine", now()))
                audit(conn, "llm", "refine", r["entry_id"], new_len=len(new))
            done.append(r["entry_id"])
        except Exception:
            failed.append(r["entry_id"])
    log_event("refine", "refine done", scanned=len(rows), adopted=len(done),
              rejected=len(failed))
    return {"refined": len(done), "failed": len(failed), "scanned": len(rows)}


# ------------------------------------------------------------------ Markdown 镜像
def render_markdown(conn) -> str:
    """把库渲染成一份人类可读、可编辑的 Markdown。"""
    docs = {r["doc_id"]: r["title"] for r in conn.execute(
        "SELECT doc_id, title FROM memory_documents")}
    rows = conn.execute(
        "SELECT e.*, g.topic FROM memory_entries e "
        "LEFT JOIN memory_groups g ON g.group_id = e.memory_group_id "
        "WHERE e.status IN ('active','pending_merge','superseded') "
        "ORDER BY coalesce(e.doc_id,''), e.l0_offset, e.version_no").fetchall()

    out = ["# Tinderbox 记忆库", "",
           f"> 导出时间 {now()} · 共 {len(rows)} 条 · {len(docs)} 份材料",
           "> 这是镜像：改了它要跑 `rebuild_from_markdown` 才会生效。", ""]
    cur_doc = object()
    for r in rows:
        doc = docs.get(r["doc_id"], "（手动写入）")
        if doc != cur_doc:
            cur_doc = doc
            out += [f"## {doc}", ""]
        flag = {"active": "现行", "pending_merge": "待裁决", "superseded": "已被取代"}[r["status"]]
        out.append(f"- **{r['category']}** · {r['created_at'][:10]} · v{r['version_no']} {flag}"
                   f" · {r['extract_state']}")
        out.append(f"  - 摘要：{r['l1_summary']}")
        if r["context"]:
            out.append(f"  - 前因：{r['context']}")
        if r["doc_id"]:
            out.append(f"  - 原文：{r['doc_id']} [{r['l0_offset']}, +{r['l0_length']})")
    return "\n".join(out) + "\n"


def write_markdown(conn, path) -> str:
    from pathlib import Path
    p = Path(path)
    p.write_text(render_markdown(conn), encoding="utf-8")
    return str(p)


META_LINE = re.compile(r"^- \*\*(\w+)\*\* · (\S+) · v(\d+) (\S+) · (\w+)$")
FIELD_LINE = re.compile(r"^  - (摘要|前因|原文)：(.*)$")


def parse_markdown(text: str) -> list[dict]:
    items, cur = [], None
    for ln in text.split("\n"):
        m = META_LINE.match(ln)
        if m:
            if cur:
                items.append(cur)
            cur = {"category": m.group(1), "date": m.group(2), "version": int(m.group(3)),
                   "status": m.group(4), "extract_state": m.group(5),
                   "summary": "", "context": "", "source": ""}
            continue
        f = FIELD_LINE.match(ln)
        if f and cur:
            key = {"摘要": "summary", "前因": "context", "原文": "source"}[f.group(1)]
            cur[key] = f.group(2).strip()
    if cur:
        items.append(cur)
    return [x for x in items if x["summary"]]


def rebuild_from_markdown(conn, path, *, user_id: str = "owner") -> dict:
    """从 Markdown 重建一个干净的库。原文指向会丢（镜像里只有 doc_id + offset）。"""
    from pathlib import Path
    items = parse_markdown(Path(path).read_text(encoding="utf-8"))
    n = 0
    for it in items:
        if it["status"] == "已被取代":
            continue
        insert_memory(conn, user_id=user_id, summary=it["summary"],
                      category=it["category"], context=it["context"],
                      confidence="medium", extract_state="refined")
        n += 1
    return {"imported": n, "scanned": len(items)}


# ------------------------------------------------------------------ 衰减 / 归档 / 回收
HALF_LIFE_DAYS = {"decision": 365, "knowledge": 180, "preference": 365, "task": 30}
TTL_VERIFIED = 180        # 被核对过的材料：原文留 180 天
TTL_UNVERIFIED = 730      # 从未核对：留 730 天
RECLAIM_GRACE = 7         # 到期后再宽限 7 天
ARCHIVE_WEIGHT = 0.05     # 权重低于此且闲置够久 → 硬归档候选


def _days_since(iso: str, now_dt) -> float:
    return (now_dt - datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ")
            .replace(tzinfo=timezone.utc)).total_seconds() / 86400


def decay(conn, *, now_dt=None, dry_run: bool = True) -> dict:
    """每日衰减：闲置越久权重越低；跌破阈值且够老就软归档。

    demo 用 created_at 当"最后一次被用到"，真实实现要用 last_accessed_at。
    """
    now_dt = now_dt or datetime.now(timezone.utc)
    rows = conn.execute(
        "SELECT entry_id, category, created_at, weight, status, pin, anchor "
        "FROM memory_entries WHERE status='active'").fetchall()
    decayed, archived = [], []
    for r in rows:
        if r["pin"] or r["anchor"]:
            continue                                   # 置顶/锚定不参与衰减
        age = _days_since(r["created_at"], now_dt)
        hl = HALF_LIFE_DAYS.get(r["category"], 180)
        target = max(ARCHIVE_WEIGHT / 2, r["weight"] * 0.5 ** (age / hl))
        if target < r["weight"] - 1e-6:
            decayed.append((r["entry_id"], r["weight"], round(target, 4)))
            if not dry_run:
                conn.execute("UPDATE memory_entries SET weight=? WHERE entry_id=?",
                             (round(target, 4), r["entry_id"]))
        if target < ARCHIVE_WEIGHT and age >= 180:
            archived.append(r["entry_id"])
    if not dry_run and archived:
        with tx(conn):
            for eid in archived:
                conn.execute("UPDATE memory_entries SET status='archived' WHERE entry_id=?", (eid,))
    return {"scanned": len(rows), "decayed": len(decayed), "would_archive": len(archived),
            "dry_run": dry_run}


def _doc_retention_days(conn, doc_id: str) -> int:
    """材料里只要有一条被核对过，就按"已核对"档留；否则按未核对档。"""
    row = conn.execute(
        "SELECT count(*) c FROM memory_entries WHERE doc_id=? AND verified_at IS NOT NULL",
        (doc_id,)).fetchone()
    return TTL_VERIFIED if row["c"] else TTL_UNVERIFIED


def reclaim(conn, *, now_dt=None, dry_run: bool = True, shrink: bool = False) -> dict:
    """四条回收触发。默认 dry_run——不可逆的事不该被顺手调用。"""
    now_dt = now_dt or datetime.now(timezone.utc)
    report = {"zero_ref": [], "all_dead": [], "expired": [], "shrunk": [],
              "freed_bytes": 0, "dry_run": dry_run}

    def blob_size(h: str) -> int:
        r = conn.execute("SELECT size FROM memory_blobs WHERE hash=?", (h,)).fetchone()
        return r["size"] if r else 0

    docs = conn.execute(
        "SELECT d.doc_id, d.blob_hash, d.expires_at, d.char_count FROM memory_documents d"
    ).fetchall()

    for d in docs:
        entries = conn.execute(
            "SELECT entry_id, status, created_at, verified_at FROM memory_entries WHERE doc_id=?",
            (d["doc_id"],)).fetchall()
        live = [e for e in entries if e["status"] in ("active", "pending_merge")]
        age = _days_since(entries[0]["created_at"], now_dt) if entries else 1e9

        # ① 零引用：材料在，但没有任何条目指向它
        if not entries:
            report["zero_ref"].append(d["doc_id"])
        # ② 全部引用已死，且都过了保留档
        elif not live and age > _doc_retention_days(conn, d["doc_id"]):
            report["all_dead"].append(d["doc_id"])
        # ③ 硬 TTL
        elif d["expires_at"]:
            try:
                exp = datetime.strptime(d["expires_at"][:19], "%Y-%m-%dT%H:%M:%S") \
                    .replace(tzinfo=timezone.utc)
            except ValueError:
                exp = None
            if exp and (now_dt - exp).days >= RECLAIM_GRACE:
                report["expired"].append(d["doc_id"])
        # ④ 瘦身：只重写原文，不动条目（默认关闭）
        elif shrink and live:
            report["shrunk"].append(d["doc_id"])

    victims = report["zero_ref"] + report["all_dead"] + report["expired"]
    # 同一段文字可能被多份材料共用（blob 去重），释放量要按**唯一** blob 计
    hashes = set()
    for doc_id in victims:
        row = conn.execute("SELECT blob_hash FROM memory_documents WHERE doc_id=?",
                           (doc_id,)).fetchone()
        if row:
            hashes.add(row["blob_hash"])
    report["freed_bytes"] = sum(blob_size(h) for h in hashes)

    if victims and not dry_run:
        with tx(conn):
            for doc_id in victims:
                row = conn.execute("SELECT blob_hash FROM memory_documents WHERE doc_id=?",
                                   (doc_id,)).fetchone()
                conn.execute("DELETE FROM memory_entries WHERE doc_id=?", (doc_id,))
                conn.execute("DELETE FROM memory_documents WHERE doc_id=?", (doc_id,))
                if row:
                    conn.execute("UPDATE memory_blobs SET ref_count = ref_count - 1 "
                                 "WHERE hash=?", (row["blob_hash"],))
            conn.execute("DELETE FROM memory_blobs WHERE ref_count <= 0")
    report["victims"] = len(victims)
    if not dry_run:
        log_event("reclaim", "reclaim applied", victims=len(victims),
                  freed_bytes=report["freed_bytes"])
    return report
