"""Tinderbox 命令行（P1：能用）。

    tbc init [--data DIR]      初始化数据目录
    tbc ingest <路径...>       导入文件/目录/stdin
    tbc search <词>            命令行检索
    tbc refine [--limit N]     LLM 精修排队中的条目
    tbc config show            打印生效配置（密钥打码）
    tbc check                  结构自检
    tbc serve [--port N]       启动看板

数据目录优先级：--data > TB_DATA > config.toml 的 data_dir > ~/.tinderbox
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402

TEXT_EXT = {".txt", ".md", ".markdown", ".org", ".rst", ".csv", ".log", ".text", ".docx"}
NEEDS_LIB = {".pdf": "pypdf", ".doc": "旧版 Word（另存为 .docx 或 .txt）"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".idea", ".vscode",
             ".tools", "out", "dist", "build_cache", "logs", "l0", "backup"}
SKIP_FILES = {"token.txt", "config.toml", "memory.db", "memory.db-wal", "memory.db-shm"}
MAX_BYTES = 5 * 1024 * 1024

DEFAULT_CONFIG = """# Tinderbox 配置（密钥只放这里或环境变量，绝不入库）
data_dir = ""

[ingest]
max_file_mb = 5
min_chars = 20
auto_refine = true

[llm]
base_url = "https://api.deepseek.com/v1"
model = "deepseek-chat"
api_key = ""            # 留空则读环境变量 LLM_API_KEY
proxy = ""              # 例：http://127.0.0.1:7897

[retention]
verified_days = 180
unverified_days = 730
shrink_enabled = false

[server]
host = "127.0.0.1"
port = 8777
"""


# ------------------------------------------------------------------ 配置与路径
def data_dir(args) -> Path:
    raw = (getattr(args, "data", None) or os.environ.get("TB_DATA")
           or read_config().get("data_dir") or (Path.home() / ".tinderbox"))
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_config() -> dict:
    cfg = {"data_dir": ""}
    path = Path(os.environ.get("TB_CONFIG") or (Path.home() / ".tinderbox" / "config.toml"))
    if not path.exists():
        return cfg
    try:
        import tomllib
        with path.open("rb") as f:
            cfg.update(tomllib.load(f))
    except Exception:
        pass
    return cfg


def boot(args) -> Path:
    """解析数据目录 + 绑路径 + 挂日志。所有命令的入口。"""
    root = data_dir(args)
    bind_paths(root)
    tb.setup_logging(root / "logs",
                     console_level="INFO" if getattr(args, "verbose", False) else "WARN")
    tb.log_event("cli", "command start", cmd=getattr(args, "cmd", "-"), data=str(root))
    return root


def bind_paths(root: Path):
    tb.DB_PATH = root / "memory.db"
    tb.ARCHIVE = root / "l0"


# ------------------------------------------------------------------ init
def cmd_init(args) -> int:
    root = data_dir(args)
    for sub in ("", "l0", "logs", "backup"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    bind_paths(root)
    conn = tb.init_db(reset=False)
    conn.close()

    cfg = root / "config.toml"
    if not cfg.exists():
        cfg.write_text(DEFAULT_CONFIG, encoding="utf-8")
    token_file = root / "token.txt"
    if not token_file.exists():
        import secrets
        token_file.write_text(secrets.token_urlsafe(18), encoding="utf-8")

    print(f"数据目录 {root}")
    print(f"  数据库 {root / 'memory.db'}")
    print(f"  配置   {cfg}")
    print(f"  令牌   {token_file}（登录看板用）")
    return 0


# ------------------------------------------------------------------ 读取文本
def docx_text(path: Path) -> str | None:
    """解 docx = zip + xml，不依赖第三方库。"""
    import html
    import re
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return None
    xml = xml.replace("</w:p>", "\n").replace("</w:tr>", "\n")
    text = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(text)


def read_text(path: Path) -> tuple[str | None, str | None]:
    """返回 (文本, 失败原因)。"""
    suffix = path.suffix.lower()
    if suffix in NEEDS_LIB:
        return None, f"不支持 {suffix}（{NEEDS_LIB[suffix]}）"
    if suffix == ".docx":
        return docx_text(path), None
    raw = path.read_bytes()
    if b"\x00" in raw[:4096]:
        return None, "二进制文件"
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore"), None


def iter_targets(paths: list[str], seen: dict | None = None, exclude: Path | None = None):
    """产出 (标题, Path 或 None)。seen 统计扩展名；exclude 是数据目录，整个跳过。"""
    for item in paths:
        if item == "-":
            yield "<stdin>", None
            continue
        p = Path(item).expanduser()
        if p.is_file():
            yield p.name, p
        elif p.is_dir():
            base = p                     # 以你给的那个目录为根
            for f in sorted(p.rglob("*")):
                if not f.is_file():
                    continue
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if f.name in SKIP_FILES:
                    continue
                if exclude is not None:
                    try:
                        f.resolve().relative_to(exclude.resolve())
                        if seen is not None:
                            seen["_excluded"] = seen.get("_excluded", 0) + 1
                        continue          # 数据目录内的文件，不导入
                    except ValueError:
                        pass
                if seen is not None:
                    ext = f.suffix.lower() or "(无扩展名)"
                    seen[ext] = seen.get(ext, 0) + 1
                if f.suffix.lower() not in TEXT_EXT:
                    continue
                yield str(f.relative_to(base)).replace("\\", "/"), f
        else:
            print(f"  ✗ 找不到：{item}")


# ------------------------------------------------------------------ ingest
def drop_document(conn, doc_id: str):
    row = conn.execute("SELECT blob_hash FROM memory_documents WHERE doc_id=?", (doc_id,)).fetchone()
    with tb.tx(conn):
        conn.execute("DELETE FROM memory_entries WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM memory_documents WHERE doc_id=?", (doc_id,))
        if row:
            conn.execute("UPDATE memory_blobs SET ref_count=ref_count-1 WHERE hash=?", (row[0],))
            conn.execute("DELETE FROM memory_blobs WHERE ref_count <= 0")


def ingest_one(conn, title: str, text: str, *, dry: bool) -> tuple[str, int]:
    """返回 (动作, 条目数)。动作：added / updated / skipped。"""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    row = conn.execute("SELECT doc_id, blob_hash FROM memory_documents WHERE title=?",
                       (title,)).fetchone()
    if row and row["blob_hash"] == digest:
        return "skipped", 0
    if dry:
        return ("updated" if row else "added"), 0
    if row:
        drop_document(conn, row["doc_id"])
        action = "updated"
    else:
        action = "added"
    res = tb.ingest(conn, text, title=title, source="file")
    return action, len(res["entries"])


def cmd_ingest(args) -> int:
    root = boot(args)
    conn = tb.connect()
    cfg = read_config().get("ingest", {})
    min_chars = int(cfg.get("min_chars", 20))
    max_bytes = int(cfg.get("max_file_mb", 5)) * 1024 * 1024

    stats = {"added": 0, "updated": 0, "skipped": 0, "failed": 0, "entries": 0}
    failures, short = [], []
    seen: dict = {}
    handled = 0
    for title, path in iter_targets(args.paths, seen, exclude=root):
        handled += 1
        try:
            if path is None:
                text = sys.stdin.read()
            else:
                if path.stat().st_size > max_bytes:
                    failures.append((title, f"超过 {max_bytes // 1024 // 1024} MB"))
                    stats["failed"] += 1
                    continue
                text, why = read_text(path)
                if text is None:
                    failures.append((title, why or "读不了"))
                    stats["failed"] += 1
                    continue
            text = text.strip()
            if len(text) < min_chars:
                stats["skipped"] += 1
                short.append((title, len(text)))
                continue
            action, n = ingest_one(conn, title, text, dry=args.dry_run)
            stats[action] += 1
            stats["entries"] += n
            mark = {"added": "+", "updated": "~", "skipped": "="}[action]
            print(f"  {mark} {title}" + ("" if args.dry_run else f"  {n} 条"))
        except Exception as e:
            failures.append((title, f"{type(e).__name__}: {e}"))
            stats["failed"] += 1

    print(f"\n新增 {stats['added']} · 更新 {stats['updated']} · 跳过 {stats['skipped']} "
          f"· 失败 {stats['failed']} · 共 {stats['entries']} 条记忆"
          + ("（dry-run，未写库）" if args.dry_run else ""))
    if handled == 0:
        excluded = seen.pop("_excluded", 0)
        print("没有找到可导入的文件。目录里实际有：")
        if excluded:
            print(f"  （其中 {excluded} 个在数据目录里，已跳过）")
        for ext, n in sorted(((k, v) for k, v in seen.items() if k != "_excluded"),
                             key=lambda x: -x[1])[:10]:
            ok = "✓ 支持" if ext in TEXT_EXT else "✗ 跳过"
            print(f"  {ext:<12}{n:>5} 个  {ok}")
        if not seen and not excluded:
            print("  （一个文件都没看到——路径对吗？）")

    tb.log_event("ingest", "import summary", added=stats["added"],
                 updated=stats["updated"], skipped=stats["skipped"],
                 failed=stats["failed"], entries=stats["entries"])
    for title, why in failures[:20]:
        tb.log_warn("ingest", "import failed", file=title, why=why)
    for title, n in short[:20]:
        tb.log_event("ingest", "skipped short", file=title, chars=n)

    if short:
        print(f"跳过（少于 {min_chars} 字）：" + "、".join(f"{t}({n})" for t, n in short[:5]))
    if failures:
        print("失败清单：")
        for title, why in failures[:10]:
            print(f"  ✗ {title}：{why}")
    conn.close()
    return 0 if stats["failed"] == 0 else 1


# ------------------------------------------------------------------ search / refine
def cmd_search(args) -> int:
    root = boot(args)
    conn = tb.connect()
    hits = tb.search(conn, " ".join(args.query), mode="hybrid", top_k=args.limit)
    if not hits:
        print("没有命中")
    for h in hits:
        print(f"  {h['score']:.3f}  [{h['category']:<10}] {h['l1_summary'][:70]}")
        print(f"         {h['created_at'][:10]} · {h['status']}")
    conn.close()
    return 0


def cmd_refine(args) -> int:
    root = boot(args)
    conn = tb.connect()
    out = tb.refine(conn, limit=args.limit)
    print(f"扫描 {out['scanned']} 条 · 采纳 {out['refined']} · 驳回 {out['failed']}")
    conn.close()
    return 0


# ------------------------------------------------------------------ config / check / serve
def cmd_config(args) -> int:
    cfg = read_config()
    root = data_dir(args)
    print(f"数据目录  {root}")
    print(f"配置文件  {Path.home() / '.tinderbox' / 'config.toml'}")
    for section, values in cfg.items():
        if not isinstance(values, dict):
            continue
        print(f"[{section}]")
        for k, v in values.items():
            shown = "***" if "key" in k and v else v
            print(f"  {k:<16}{shown}")
    return 0


def cmd_check(args) -> int:
    root = boot(args)
    conn = tb.connect()
    st = tb.stats(conn)
    print(f"材料 {st['documents']} · 条目 {st['entries']} · L0 {st['l0_bytes']:,} 字节")
    print(f"FTS active {st['fts_active']} · history {st['fts_history']}")
    orphan = conn.execute(
        "SELECT count(*) c FROM memory_entries e LEFT JOIN memory_documents d "
        "ON d.doc_id=e.doc_id WHERE e.doc_id IS NOT NULL AND d.doc_id IS NULL").fetchone()["c"]
    neg = conn.execute("SELECT count(*) c FROM memory_blobs WHERE ref_count<0").fetchone()["c"]
    live = st["active"] + st["pending_merge"]
    ok = orphan == 0 and neg == 0 and st["fts_active"] == live
    print(f"孤儿条目 {orphan} · 负引用 {neg} · 索引一致 {'是' if st['fts_active'] == live else '否'}")
    print("→ 通过" if ok else "→ 有问题")
    conn.close()
    return 0 if ok else 1


def cmd_serve(args) -> int:
    root = boot(args)
    os.environ["TB_DATA"] = str(root)
    os.environ.setdefault("TB_PORT", str(args.port))
    import web
    print(f"看板 http://127.0.0.1:{args.port}")
    web.run(port=args.port)
    return 0


# ------------------------------------------------------------------ 入口
def main() -> int:
    ap = argparse.ArgumentParser(prog="tbc", description="Tinderbox 命令行")
    ap.add_argument("--data", help="数据目录")
    ap.add_argument("-v", "--verbose", action="store_true", help="日志同时打到控制台")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)

    p = sub.add_parser("ingest")
    p.add_argument("paths", nargs="+")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("search")
    p.add_argument("query", nargs="+")
    p.add_argument("--limit", type=int, default=8)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("refine")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_refine)

    p = sub.add_parser("config")
    p.add_argument("action", choices=["show"], nargs="?", default="show")
    p.set_defaults(func=cmd_config)

    sub.add_parser("check").set_defaults(func=cmd_check)

    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8777)
    p.set_defaults(func=cmd_serve)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
