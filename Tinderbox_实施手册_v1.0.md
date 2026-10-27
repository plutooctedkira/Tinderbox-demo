# Tinderbox 实施手册

> 只讲**怎么把它做出来**。设计理由与 19 轮修订的来龙去脉在《参考卷》里。

## 一页纸

**它是什么**：本地优先的个人记忆库。把聊天/笔记/录音里的“决定、偏好、任务、知识”提炼成记忆，
按版本链管理“改口”，中文检索，原文冷存按需取回。

**一句话**：记忆是摘要，原文是证据；摘要可以失效，证据不能丢。

**四条铁律**

| # | 铁律 | 违反的后果 |
|---|---|---|
| 1 | 高危动作不自动执行：覆盖/合并只挂起，等人裁决 | 旧结论被静默作废 |
| 2 | L1 写"结论 + 依据"，不是截断的原文 | 三个月后没人记得为什么 |
| 3 | 链首必须带前因（`context`），后续版本只交代差异 | 整条链悬空 |
| 4 | 原文只存一份，条目靠 offset 指过去 | 库体积爆炸、摘要与原文不一致 |

**六步主流程**：`入库 → 分块 → 提炼 L1 → 冲突检测 → 挂起/裁决 → 检索`

**三条最容易写错的**：分块上限必须生效；没有空行要回退到单行/句末；简繁归一必须在分词入口做。

**工期**：P0 6 天 + P1 11 天 + P2 4 天 ≈ 21 人日。

---

## 5 数据模型（建表语句）

> 完整字段说明与索引清单见《参考卷》第 5 章。这里只保留建表语句。

### 5.1 实体关系概览
```
memory_groups 1 ──── n memory_entries
                              │
                              ├─ 1 : 0..1 ── memory_documents ───┐
                              │                                  │
                              ├─ 1 : 0..1 ── memory_media ───────┤
                              │                                  │
                              ├─ n : n ───── memory_conflicts    │
                              │                                  ▼
                              └─ 1 : n ───── memory_logs     memory_blobs
                                                             （hash 去重）
memory_entries ──(硬归档)──▶ memory_entries_archive
```
### 5.2 连接与全局 PRAGMA
```sql
-- 每个连接建立后立即执行（db.py: get_db_connection）
PRAGMA journal_mode       = WAL;      -- 多读单写，读写不互斥
PRAGMA synchronous        = NORMAL;   -- WAL 下兼顾安全与吞吐
PRAGMA foreign_keys       = ON;       -- 打开外键（SQLite 默认关闭）
PRAGMA busy_timeout       = 30000;    -- 30 s 忙等，配合 WAL
PRAGMA wal_autocheckpoint = 1000;     -- 约 4 MB 触发检查点
PRAGMA temp_store         = MEMORY;   -- 临时表进内存，加速排序
PRAGMA mmap_size          = 268435456;-- 256 MB 内存映射，提升只读性能
PRAGMA cache_size         = -16384;   -- 16 MB 页缓存
```
### 5.3 元数据表
```sql
CREATE TABLE memory_schema_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

INSERT OR IGNORE INTO memory_schema_meta(key, value) VALUES ('schema_version','2.24.0');
```
### 5.4 主表 memory_entries
```sql
CREATE TABLE memory_entries (
    -- 物理主键：INTEGER PRIMARY KEY，保证 rowid 稳定（VACUUM 不改写），
    -- 同时作为三个 FTS 表的 rowid，实现 O(1) 的增删
    row_id            INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 业务标识
    entry_id          TEXT    NOT NULL UNIQUE,          -- mem-<12位十六进制>
    user_id           TEXT    NOT NULL DEFAULT 'owner',  -- 所有者身份，与部署位置无关；不参与过滤，见 2.4
    session_id        TEXT,

    -- 版本链
    memory_group_id   TEXT    NOT NULL REFERENCES memory_groups(group_id) ON DELETE RESTRICT,
    root_id           TEXT    NOT NULL,
    version_no        INTEGER NOT NULL DEFAULT 1 CHECK (version_no >= 1),
    predecessor_id    TEXT,
    superseded_by     TEXT,

    -- 语义
    category          TEXT    NOT NULL CHECK (category IN
                          ('preference','task','decision','knowledge','fiction_inspiration')),
    type              TEXT,
    l1_summary        TEXT    NOT NULL CHECK (length(l1_summary) BETWEEN 1 AND 4000),
    tokenized_content TEXT    NOT NULL DEFAULT '',
    l1_hash           TEXT    NOT NULL,                 -- sha256(l1_summary) 前 16 位，用于去重
    context           TEXT    NOT NULL DEFAULT '',      -- 前因：仅链首填充（见 6.6.3）

    -- L0 引用（一份材料一个文件，条目只记区间）
    doc_id            TEXT    REFERENCES memory_documents(doc_id) ON DELETE RESTRICT,
    l0_offset         INTEGER,                          -- 该条 L1 在原文中的起始字符偏移
    l0_length         INTEGER,                          -- 覆盖的字符数
    chunk_index       INTEGER,                          -- 来自第几块（0 起），追溯与排序用
    l0_state          TEXT    NOT NULL DEFAULT 'none'   -- 从所属文档同步的快照
                          CHECK (l0_state IN ('none','live','purged')),

    -- 媒体
    media_id          TEXT    REFERENCES memory_media(media_id) ON DELETE SET NULL,

    -- 来源与可信度
    source            TEXT    NOT NULL DEFAULT 'conversation'
                          CHECK (source IN ('conversation','recording','obsidian','api','import')),
    confidence        TEXT    NOT NULL DEFAULT 'medium',
    extract_state     TEXT    NOT NULL DEFAULT 'provisional',  -- provisional / refined / failed
    refined_at        TEXT,                            -- 精修完成时间
                          CHECK (confidence IN ('high','medium','low')),
    importance        REAL    NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0 AND 1),

    -- 验证状态（决定所属 L0 的保留档位）
    verified_at       TEXT,                             -- 被人工确认/编辑/裁决的时间
    verified_by       TEXT,
    verified_reason   TEXT    CHECK (verified_reason IN
                          ('authored','adjudicated','reviewed')),

    -- 生命周期
    status            TEXT    NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active','completed','pending_merge',
                                            'archived','superseded','purged')),
    pin               INTEGER NOT NULL DEFAULT 0 CHECK (pin    IN (0,1)),
    anchor            INTEGER NOT NULL DEFAULT 0 CHECK (anchor IN (0,1)),
    weight            REAL    NOT NULL DEFAULT 1.0 CHECK (weight BETWEEN 0 AND 1),
    access_count      INTEGER NOT NULL DEFAULT 0,

    -- 事实有效期
    valid_from        TEXT,
    valid_to          TEXT,

    -- 时间戳（UTC ISO-8601，毫秒精度）
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_accessed_at  TEXT,

    UNIQUE (memory_group_id, version_no),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from)
);

-- 建表顺序：memory_documents 必须先于 memory_entries（外键前向引用）
```
### 5.5 版本组表 memory_groups
```sql
CREATE TABLE memory_groups (
    group_id          TEXT PRIMARY KEY,                  -- g-<12位十六进制>
    root_id           TEXT NOT NULL UNIQUE,              -- 首条 entry_id
    user_id           TEXT NOT NULL,
    topic             TEXT NOT NULL,                     -- 由首条 L1 生成的短标题（≤ 60 字）
    category          TEXT,
    current_version_no INTEGER NOT NULL DEFAULT 1,
    entry_count       INTEGER NOT NULL DEFAULT 1,
    is_open           INTEGER NOT NULL DEFAULT 1 CHECK (is_open IN (0,1)),
    merged_into       TEXT,                              -- 冲突裁决"合并"时指向目标组
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
```
### 5.6 物理文件登记表 memory_blobs
```sql
CREATE TABLE memory_blobs (
    hash         TEXT PRIMARY KEY,                       -- sha256(未压缩字节) 全 64 位
    kind         TEXT NOT NULL CHECK (kind IN ('l0','audio','video','transcript','doc')),
    storage_path TEXT NOT NULL,                          -- archive/l0/<hash>.zst，相对路径
    compression  TEXT NOT NULL DEFAULT 'zstd'
                    CHECK (compression IN ('none','gzip','zstd')),
    mime         TEXT,
    raw_size     INTEGER NOT NULL,
    size         INTEGER NOT NULL,                       -- 压缩后字节数
    ref_count    INTEGER NOT NULL DEFAULT 0 CHECK (ref_count >= 0),
    state        TEXT NOT NULL DEFAULT 'live'
                    CHECK (state IN ('live','orphan','purged')),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    expires_at   TEXT,
    purged_at    TEXT
);
```
### 5.7 材料表 memory_documents
```sql
CREATE TABLE memory_documents (
    doc_id          TEXT PRIMARY KEY,                     -- d-<12位十六进制>
    user_id         TEXT NOT NULL,
    title           TEXT,                                 -- 标题 / 会话摘要 / 录音名
    source          TEXT NOT NULL
                      CHECK (source IN ('conversation','recording','obsidian','api','import')),
    mime            TEXT,
    blob_hash       TEXT NOT NULL REFERENCES memory_blobs(hash) ON DELETE RESTRICT,
    char_count      INTEGER NOT NULL,
    raw_size        INTEGER NOT NULL,
    compressed_size INTEGER NOT NULL,
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    entry_count     INTEGER NOT NULL DEFAULT 0,
    live_ref_count  INTEGER NOT NULL DEFAULT 0,           -- 仍为 active/completed 的条目数，每晚刷新
    state           TEXT NOT NULL DEFAULT 'live'
                      CHECK (state IN ('live','shrunk','purged')),
    restore_count   INTEGER NOT NULL DEFAULT 0,
    last_restored_at TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    expires_at      TEXT,
    last_pruned_at  TEXT                                   -- 最后一次瘦身/回收时间
);
```
### 5.8 媒体表 memory_media
```sql
CREATE TABLE memory_media (
    media_id          TEXT PRIMARY KEY,                  -- m-<12位十六进制>
    entry_id          TEXT,                              -- 可空：转写完成后回填
    user_id           TEXT NOT NULL,
    media_type        TEXT NOT NULL CHECK (media_type IN ('audio','video','image','doc')),
    blob_hash         TEXT NOT NULL REFERENCES memory_blobs(hash) ON DELETE RESTRICT,
    mime              TEXT,
    duration_sec      REAL,
    sample_rate       INTEGER,
    channels          INTEGER,
    asr_provider      TEXT,                              -- faster-whisper / openai / deepseek
    asr_model         TEXT,
    asr_lang          TEXT,
    speaker_count     INTEGER,
    transcript_state  TEXT NOT NULL DEFAULT 'pending'
                        CHECK (transcript_state IN
                          ('pending','queued','running','done','failed','skipped')),
    transcript_doc_id TEXT    REFERENCES memory_documents(doc_id) ON DELETE SET NULL,
                                                         -- 转写全文本身是一份 L0 文档
    transcript_chars  INTEGER,
    recorded_at       TEXT,
    uploaded_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    transcribed_at    TEXT,
    expires_at        TEXT,                              -- 音频 TTL（默认 180 天）
    error_message     TEXT
);
```
### 5.9 冲突表 memory_conflicts
```sql
CREATE TABLE memory_conflicts (
    conflict_id      TEXT PRIMARY KEY,                   -- c-<12位十六进制>
    group_id         TEXT REFERENCES memory_groups(group_id) ON DELETE SET NULL,
    old_entry_id     TEXT NOT NULL,
    new_entry_id     TEXT NOT NULL,
    relation         TEXT NOT NULL CHECK (relation IN
                       ('unrelated','complement','override','duplicate')),
    similarity       REAL NOT NULL,                      -- 召回相似度 0~1
    llm_confidence   REAL,                               -- LLM 判定置信度 0~1
    llm_reason       TEXT,
    suggested_action TEXT CHECK (suggested_action IN
                       ('supersede','merge','keep_both','ignore')),
    state            TEXT NOT NULL DEFAULT 'open'
                       CHECK (state IN ('open','resolved','ignored')),
    resolution       TEXT CHECK (resolution IN
                       ('supersede','merge','keep_both','ignore')),
    resolved_by      TEXT,                               -- user_id 或 'auto'
    resolved_at      TEXT,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (old_entry_id, new_entry_id)
);
```
### 5.10 审计日志表 memory_logs
```sql
CREATE TABLE memory_logs (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id   TEXT,
    group_id   TEXT,
    media_id   TEXT,
    action     TEXT NOT NULL CHECK (action IN (
                 'INSERT','UPDATE','FIELD_DIFF',
                 'SUPERSEDE','SOFT_DELETE','RESTORE','PURGE',
                 'DECAY','ARCHIVE','HARD_ARCHIVE','RECALL_HIT',
                 'UPLOAD_AUDIO','TRANSCRIBE',
                 'L0_ARCHIVE','L0_RESTORE','L0_PURGE',
                 'CONFLICT_DETECT','CONFLICT_RESOLVE','EXPORT')),
    old_value  TEXT,                                     -- JSON 快照
    new_value  TEXT,                                     -- JSON 快照
    source     TEXT,
    actor      TEXT NOT NULL DEFAULT 'system'
                 CHECK (actor IN ('trigger','api','mcp','scheduler','llm','cli')),
    ts         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
```
### 5.11 冷归档条目表 memory_entries_archive
```sql
-- 归档表的列、约束、默认值与 memory_entries 完全一致，只多一列 archived_at。
-- 不要用 CREATE TABLE AS SELECT：它不复制主键、CHECK、默认值，主表加列时要靠人记得重建。
-- 迁移脚本的做法：拷贝 5.4 的 DDL → 改表名 → 追加 archived_at 一列。
CREATE TABLE memory_entries_archive ( ...同 memory_entries... ,
    archived_at TEXT );
ALTER TABLE memory_entries_archive ADD COLUMN archive_reason TEXT;  -- weight_low / ttl / manual
CREATE INDEX idx_archive_archived_at ON memory_entries_archive(archived_at);
```
```sql
CREATE TRIGGER trg_fts_archive_ai AFTER INSERT ON memory_entries_archive BEGIN
    INSERT INTO memory_fts_archive(rowid, l1_summary, keywords, tokenized_content)
    VALUES (new.row_id, new.l1_summary, new.keywords, new.tokenized_content);
END;

CREATE TRIGGER trg_fts_archive_ad AFTER DELETE ON memory_entries_archive BEGIN
    DELETE FROM memory_fts_archive WHERE rowid = old.row_id;
END;
```
### 5.12 FTS5 全文索引
```sql
-- 当前有效记忆
CREATE VIRTUAL TABLE memory_fts_active USING fts5(
    entry_id          UNINDEXED,
    tokenized_content,
    tokenize = "unicode61 remove_diacritics 2"
);

-- 历史记忆（superseded / archived），供"历史追问"
CREATE VIRTUAL TABLE memory_fts_history USING fts5(
    entry_id          UNINDEXED,
    tokenized_content,
    tokenize = "unicode61 remove_diacritics 2"
);

-- 冷归档条目
CREATE VIRTUAL TABLE memory_fts_archive USING fts5(
    entry_id          UNINDEXED,
    tokenized_content,
    tokenize = "unicode61 remove_diacritics 2"
);
```
### 5.13 索引清单
```sql
CREATE INDEX idx_entries_status   ON memory_entries(status);
CREATE INDEX idx_entries_group_version ON memory_entries(memory_group_id, version_no);
CREATE INDEX idx_entries_status_weight ON memory_entries(status, weight);
CREATE INDEX idx_entries_l0_state      ON memory_entries(l0_state);
CREATE INDEX idx_entries_media         ON memory_entries(media_id);
CREATE INDEX idx_entries_updated       ON memory_entries(updated_at DESC);
CREATE INDEX idx_entries_l1_hash       ON memory_entries(l1_hash);
CREATE INDEX idx_media_entry           ON memory_media(entry_id);
CREATE INDEX idx_media_hash            ON memory_media(blob_hash);
CREATE INDEX idx_media_expires         ON memory_media(expires_at);
CREATE INDEX idx_docs_expires         ON memory_documents(expires_at);
CREATE INDEX idx_docs_live_ref        ON memory_documents(state, live_ref_count);
CREATE INDEX idx_entries_doc          ON memory_entries(doc_id);
CREATE INDEX idx_blobs_state           ON memory_blobs(state, expires_at);
CREATE INDEX idx_conflicts_state       ON memory_conflicts(state, created_at);
CREATE INDEX idx_logs_entry_ts         ON memory_logs(entry_id, ts);
CREATE INDEX idx_logs_action_ts        ON memory_logs(action, ts);
```
### 5.14 触发器：FTS 同步（3 个）
```sql
-- 1) 插入：按状态路由到 active 或 history
CREATE TRIGGER trg_fts_ai AFTER INSERT ON memory_entries
WHEN NEW.tokenized_content <> ''
BEGIN
    INSERT INTO memory_fts_active(rowid, entry_id, tokenized_content)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized_content
        WHERE NEW.status = 'active';

    INSERT INTO memory_fts_history(rowid, entry_id, tokenized_content)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized_content
        WHERE NEW.status IN ('superseded','archived');
END;
```
```sql
-- 2) 更新：仅当 status 或 tokenized_content 真正变化时重建
--    （访问计数、权重、pin 等高频更新绝不触发，避免无谓索引写放大）
CREATE TRIGGER trg_fts_au
AFTER UPDATE OF status, tokenized_content ON memory_entries
WHEN OLD.status IS NOT NEW.status
  OR OLD.tokenized_content IS NOT NEW.tokenized_content
BEGIN
    DELETE FROM memory_fts_active  WHERE rowid = NEW.row_id;
    DELETE FROM memory_fts_history WHERE rowid = NEW.row_id;

    INSERT INTO memory_fts_active(rowid, entry_id, tokenized_content)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized_content
        WHERE NEW.status = 'active' AND NEW.tokenized_content <> '';

    INSERT INTO memory_fts_history(rowid, entry_id, tokenized_content)
        SELECT NEW.row_id, NEW.entry_id, NEW.tokenized_content
        WHERE NEW.status IN ('superseded','archived')
          AND NEW.tokenized_content <> '';
END;
```
```sql
-- 3) 删除：两个索引同时清理
CREATE TRIGGER trg_fts_ad AFTER DELETE ON memory_entries
BEGIN
    DELETE FROM memory_fts_active  WHERE rowid = OLD.row_id;
    DELETE FROM memory_fts_history WHERE rowid = OLD.row_id;
END;
```
### 5.15 触发器：审计（3 个）
```sql
CREATE TRIGGER trg_audit_ai AFTER INSERT ON memory_entries
BEGIN
    INSERT INTO memory_logs(entry_id, group_id, media_id, action, new_value, source, actor)
    VALUES (
        NEW.entry_id, NEW.memory_group_id, NEW.media_id, 'INSERT',
        json_object(
            'status', NEW.status, 'category', NEW.category,
            'l1_summary', substr(NEW.l1_summary, 1, 200),
            'weight', NEW.weight, 'version_no', NEW.version_no,
            'source', NEW.source,
            'confidence', NEW.confidence, 'important', NEW.importance),
        NEW.source, 'trigger');
END;
```
```sql
-- 只在这几列变化时写审计；weight/access_count 是高频更新，不该触发审计
CREATE TRIGGER trg_audit_au AFTER UPDATE OF status, l1_summary, pin, anchor,
                                    valid_to, l0_state ON memory_entries
WHEN OLD.status      IS NOT NEW.status
  OR OLD.l1_summary  IS NOT NEW.l1_summary
  OR OLD.pin         IS NOT NEW.pin
  OR OLD.anchor      IS NOT NEW.anchor
  OR OLD.valid_to    IS NOT NEW.valid_to
  OR OLD.l0_state    IS NOT NEW.l0_state
BEGIN
    INSERT INTO memory_logs(entry_id, group_id, media_id, action, old_value, new_value, source, actor)
    VALUES (
        NEW.entry_id, NEW.memory_group_id, NEW.media_id, 'FIELD_DIFF',
        json_object('status', OLD.status, 'pin', OLD.pin, 'anchor', OLD.anchor,
                    'l0_state', OLD.l0_state, 'valid_to', OLD.valid_to,
                    'l1_head', substr(OLD.l1_summary, 1, 200)),
        json_object('status', NEW.status, 'pin', NEW.pin, 'anchor', NEW.anchor,
                    'l0_state', NEW.l0_state, 'valid_to', NEW.valid_to,
                    'l1_head', substr(NEW.l1_summary, 1, 200)),
        NEW.source, 'trigger');
END;
```
```sql
CREATE TRIGGER trg_audit_ad AFTER DELETE ON memory_entries
BEGIN
    INSERT INTO memory_logs(entry_id, group_id, action, old_value, source, actor)
    VALUES (
        OLD.entry_id, OLD.memory_group_id, 'PURGE',
        json_object('status', OLD.status, 'weight', OLD.weight,
                    'l1_head', substr(OLD.l1_summary, 1, 200)),
        OLD.source, 'trigger');
END;
```
### 5.16 触发器与索引数量核对
### 5.17 完整性自检
```sql
-- 1) 外键一致性（应为空集）
PRAGMA foreign_key_check;

-- 2) FTS 与主表行数一致性
SELECT 'active',  (SELECT count(*) FROM memory_entries WHERE status='active')
              - (SELECT count(*) FROM memory_fts_active)
UNION ALL
SELECT 'history', (SELECT count(*) FROM memory_entries
                    WHERE status IN ('superseded','archived'))
              - (SELECT count(*) FROM memory_fts_history);

-- 3) 版本组约束：每组至多一个 active
SELECT memory_group_id, count(*) FROM memory_entries
 WHERE status='active' GROUP BY memory_group_id HAVING count(*) > 1;

-- 4) 归档表列集合与主表一致（Python 侧比对 PRAGMA table_info）
```
```sql
INSERT INTO memory_fts_active(memory_fts_active)  VALUES('integrity-check');
INSERT INTO memory_fts_history(memory_fts_history) VALUES('integrity-check');
INSERT INTO memory_fts_active(memory_fts_active)  VALUES('optimize');
INSERT INTO memory_fts_history(memory_fts_history) VALUES('optimize');
```
### 5.18 向量索引 memory_vectors
```sql
-- 需要 sqlite-vec 扩展（v0.1.6+）
-- 预留设计：向量检索未排期，当前**不建这张表**；启用时同步打开 附录 A 的 EMBED_*
CREATE VIRTUAL TABLE memory_vectors USING vec0(
    row_id    INTEGER PRIMARY KEY,          -- 与 memory_entries.row_id 对齐
    embedding int8[1024]                    -- bge-m3，int8 量化，体积为 float32 的 1/4
);
```
### 5.19 概念层 memory_concepts
```sql
CREATE TABLE memory_concepts(
    concept_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    parent_id  TEXT REFERENCES memory_concepts(concept_id) ON DELETE SET NULL,
    level      INTEGER NOT NULL DEFAULT 0,
    kind       TEXT NOT NULL DEFAULT 'manual'
                 CHECK (kind IN ('manual','derived','proposed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE memory_entry_concepts(
    entry_id    TEXT NOT NULL REFERENCES memory_entries(entry_id) ON DELETE CASCADE,
    concept_id  TEXT NOT NULL REFERENCES memory_concepts(concept_id) ON DELETE CASCADE,
    confidence  REAL NOT NULL DEFAULT 1.0,
    assigned_by TEXT NOT NULL DEFAULT 'manual'
                  CHECK (assigned_by IN ('manual','rule','vector')),
    is_seed     INTEGER NOT NULL DEFAULT 0,   -- 人指定的锚点，质心只按它算（见 6.15）
    PRIMARY KEY (entry_id, concept_id)
);
```
### 5.20 记忆关系表 memory_relations
```sql
CREATE TABLE memory_relations(
    relation_id TEXT PRIMARY KEY,
    from_entry  TEXT NOT NULL REFERENCES memory_entries(entry_id) ON DELETE CASCADE,
    to_entry    TEXT NOT NULL REFERENCES memory_entries(entry_id) ON DELETE CASCADE,
    relation    TEXT NOT NULL
                  CHECK (relation IN ('complement','related','derived_from')),
    confidence  REAL,
    reason      TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (from_entry, to_entry)
);
```
### 5.21 修订留痕 memory_revisions
```sql
CREATE TABLE memory_revisions(
    revision_id TEXT PRIMARY KEY,
    entry_id    TEXT NOT NULL REFERENCES memory_entries(entry_id) ON DELETE CASCADE,
    old_summary TEXT NOT NULL,
    new_summary TEXT NOT NULL,
    reason      TEXT,                    -- llm_refine / manual / repair
    created_at  TEXT NOT NULL
);
```
### 5.22 Markdown 镜像
```markdown
## 露营咖啡车项目记录

- **decision** · 2026-10-27 · v2 现行 · refined
  - 摘要：首站从大学城改为创业园区——因为日均只有 34 杯
  - 前因：项目最初计划把面包车改成咖啡车
  - 原文：d-3f2a [181, +120)
```

---

## 2 目标与非目标

### 2.1 产品定位

Tinderbox 是一个**面向长期运行的本地优先记忆引擎**：把对话、决策、知识、灵感与录音，压缩成可检索的短摘要（L1）常驻 SQLite，把原始全文与音视频压成冷归档（L0）存入文件系统，并通过版本链与冲突治理，保证“记忆随时间演化而不互相污染”。

> 名字取自安徒生《打火匣》（Fyrtøjet，1835）：士兵擦一下火石，就有一条狗跳出来，把他想要的东西叼回来——先是眼睛像茶杯大的那条，然后是磨盘大的，最后是圆塔大的。
>
> 记忆库要做的正是这件事：**你擦一下（问一句），它把你要的那条记忆叼回来**。至于那匣子本身，平时只是静静躺在口袋里。

它同时服务三类消费者：

- **AI 编码代理**：通过 MCP 协议读写记忆，跨会话保持上下文；
- **人**：通过 Web 看板检索、审阅、裁决冲突、恢复原文；
- **知识与写作工具**：通过 Obsidian 仓库与 Git，形成可版本控制、可双链的外部副本。

### 2.2 要解决的问题

| 问题 | 表现 | 本方案的解法 |
|---|---|---|
| 上下文窗口有限 | 长会话/长文档塞不进 prompt | L1 摘要常驻 + L0 原文冷存，按需恢复 |
| 记忆互相污染 | 新旧事实并存，模型取到过期结论 | 版本链（group/version/predecessor）+ 状态机 + 双 FTS |
| 中文检索失效 | `unicode61` 把整句汉字当一个 token，检索不到词 | jieba 预分词写入 `tokenized_content` |
| 库无限膨胀 | 全部原文留在主库 | 分级存储 + 压缩冷归档 + TTL |
| 冲突无处置 | 相似记忆反复出现，无人裁决 | `conflict_guard` 判定 + `pending_merge` + 人工裁决 |
| 录音不可用 | 会议/口述内容无法进入记忆 | ASR 适配层 + 媒体表 + 转写管道 |
| 写入不安全 | supersede 非原子，并发下断链 | 单事务 + 乐观锁（`version_no`） |

### 2.3 目标（可验收）

| 编号 | 目标 | 验收指标 |
|---|---|---|
| G1 | 中文检索可用 | 200 条查询集上 Recall@10 ≥ 0.90（混合检索），纯 FTS 分路 ≥ 0.85，优于未分词基线 ≥ 15 个百分点 |
| G2 | 记忆不污染 | **自动挂起部分的精确率 ≥ 0.85**（宁可少挂，不可错挂）；并集召回率另计；误归档率 ≤ 2% |
| G3 | 存储可控 | 10 万条记忆主库 ≤ 400 MB；L0 压缩比 ≥ 3:1（文本） |
| G4 | 检索够快 | 10 万条规模下混合检索 `p95` ≤ 300 ms（查询向量缓存命中 ≤ 120 ms）；纯 FTS 降级路径 ≤ 150 ms |
| G5 | 数据不丢 | L0/媒体 TTL 清理前有宽限期与回收站；`pin/anchor` 永不清理 |
| G6 | 成本可控 | 相比“全文常驻 prompt”，同等会话的 Token 消耗下降 ≥ 60% |
| G7 | 可挂载 | MCP 工具在 Cline/Claude Desktop 中可直接列出并调用 |

## 3 术语与分层模型

### 3.1 术语表

| 术语 | 含义 |
|---|---|
| **L1** | 一级记忆：由 LLM 从原文提炼的短摘要（默认 ≤ 400 字），`NOT NULL`，常驻主库，参与全文检索与排序 |
| **L0** | 零级记忆：产生 L1 的原始片段（对话原文、录音转写、导入文档片段），压缩后存文件系统，主库只存引用 |
| **条目 Entry** | 一条 L1 记忆，`entry_id` 标识，是检索与展示的最小单位 |
| **版本组 Group** | 同一话题/事实的条目集合，`memory_group_id` 标识，组内按 `version_no` 递增 |
| **根 Root** | 版本组的第一条（`version_no = 1`），其 `entry_id` 即 `root_id` |
| **前驱 Predecessor** | 组内上一条，`predecessor_id` 指向前驱 `entry_id` |
| **取代 Supersede** | 用新条目替代旧条目的语义，旧条目 `status='superseded'`、`superseded_by` 指向新条目 |
| **冲突 Conflict** | 两条记忆语义重叠但归属未定，进入 `pending_merge` 等待裁决 |
| **冷归档 Cold Archive** | 压缩后落盘、按需解压的 L0/媒体存储形态 |
| **TTL** | 冷归档的存活期，到期物理删除 |
| **Blob** | 文件系统上的一个物理文件，以内容哈希 `hash` 唯一标识，可被多个条目共享 |
| **加权 BM25** | FTS5 的 `bm25()` 排序函数，配合列权重与自定义加权得到最终得分 |
| **已核对 Verified** | 摘要被**人**确认过（自己写、裁决确认、逐条复核），`verified_at` 非空。只影响原文保留期，不影响排序 |
| **置顶 / 锚定** | 用户对记忆的**组织手段**：置顶提升排序并按需豁免清理，锚定豁免衰减。二者都**不**代表内容已被核对 |

### 3.2 三层记忆模型

```
┌──────────────────────────────────────────────────────────────┐
│  L1  摘要层（SQLite）                                          │
│  l1_summary · tokenized_content · weight · valid_from/to      │
│  常驻内存/磁盘，全文检索，参与排序                              │
│  体量：每条 0.2 ~ 0.5 KB                                       │
├──────────────────────────────────────────────────────────────┤
│  L0  原文层（文件系统，压缩）                                   │
│  archive/l0/<hash>.zst · memory_documents · memory_blobs       │
│  一份材料一个文件；条目用 offset/length 指向区间                │
│  体量：整份压缩，约为原文的 1/3.5                                │
├──────────────────────────────────────────────────────────────┤
│  M   媒体层（文件系统，压缩/转码）                              │
│  archive/audio/<hash>.opus · memory_media                      │
│  ASR 转写后再走 ingest 生成 L1                                  │
│  体量：每小时录音 8 ~ 15 MB（opus 24 kbps 单声道）              │
└──────────────────────────────────────────────────────────────┘
```

三层之间的唯一入口是 `storage.insert_memory()` 与 `archive_manager.put_document()`，其余模块不允许直接写文件系统或直接 `INSERT` 到 `memory_entries`。

注意层级之间是**多对一**：一份 L0 会产出多条 L1（一份 5 万字的文档 ≈ 20 条摘要），因此 L0 不是“每条的原文”，而是“这批条目共同的出处”。

### 3.3 版本链模型

一个话题第一次被记住时，创建版本组：

```
group: g-7f3a  topic="部署环境"   current_version_no=3
  ├─ mem-a1  v1  status=superseded  superseded_by=mem-b2  predecessor=NULL
  ├─ mem-b2  v2  status=superseded  superseded_by=mem-c3  predecessor=mem-a1
  └─ mem-c3  v3  status=active      superseded_by=NULL   predecessor=mem-b2
```

约束：

- 组内 `(memory_group_id, version_no)` 唯一；
- 组内至多 **一条** `status='active'`（由 `storage.supersede_memory()` 的事务保证）；
- `predecessor_id` 与 `superseded_by` 必须互为逆向（同事务内成对写入）；
- 删除/归档只改 `status`，不物理删除条目；物理删除仅发生在 L0/媒体与 `memory_entries_archive`。

## 4 总体架构

### 4.1 分层架构

```
┌──────────────────────────── 消费者 ────────────────────────────┐
│  AI 代理 (Cline / Claude Desktop)   Web 看板   Obsidian+Git  │
└───────────┬──────────────────────────┬──────────┬──────────────┘
            │ MCP (stdio)              │ HTTP     │ 文件 + git
┌───────────▼──────────────┐ ┌─────────▼──────────▼──────────────┐
│  mcp_server.py           │ │  dashboard.py  (:8765)            │
│  12 个工具                │ │  鉴权 · 路由 · 参数校验 · 限流      │
└───────────┬──────────────┘ └─────────┬─────────────────────────┘
            │                          │
┌───────────▼──────────────────────────▼─────────────────────────┐
│                      服务层 src/service                        │
│  storage.py     ingest.py      retriever.py    decay.py        │
│  version_chain  conflict_guard media_ingest    archive_manager │
│  asr_adapter    textproc.py    config.py                       │
└───────────┬────────────────────────────────────┬───────────────┘
            │                                    │
┌───────────▼─────────────────┐   ┌──────────────▼───────────────┐
│  SQLite memory.db (WAL)     │   │  文件系统                     │
│  memory_entries             │   │  archive/l0/<hash>.zst       │
│  memory_groups              │   │  archive/audio/<hash>.opus   │
│  memory_blobs               │   │  archive/transcripts/…       │
│  memory_documents           │   │  cache/restore/ (临时)        │
│  memory_media               │   │  vault/ (Obsidian .md)       │
│  memory_conflicts           │   └──────────────────────────────┘
│  memory_logs                │
│  memory_entries_archive     │   ┌──────────────────────────────┐
│  memory_fts_active          │   │  DeepSeek API (LLM)          │
│  memory_fts_history         │◄──┤  faster-whisper / ASR API    │
│  memory_fts_archive         │   └──────────────────────────────┘
└─────────────────────────────┘
```

### 4.2 进程模型

| 进程 | 启动方式 | 职责 | 并发模型 |
|---|---|---|---|
| `dashboard.py` | systemd 常驻 | HTTP API + 静态看板 | `ThreadingHTTPServer`，每连接一线程，每线程独立 SQLite 连接 |
| `mcp_server.py` | 由客户端拉起（stdio） | MCP 工具 | 单线程事件循环，每次调用短连接 |
| `maintenance` | cron / systemd timer | 衰减、归档、TTL、对账 | 单进程 + `flock` 互斥，禁止并发运行 |
| `media_worker` | systemd 常驻（可选） | ASR 队列消费 | 单消费者，串行处理 |

**互斥约定**：`maintenance` 与 `media_worker` 各自持有独立的 `flock` 文件（`var/maintenance.lock`、`var/media.lock`），避免定时任务重叠。

## 6 模块设计

### 6.1 模块总表

| 模块 | 状态 | 优先级 | 职责 | 主要对外函数 | 依赖 |
|---|---| ★ 核心 |---|---|---|---|
| `config.py` | 新增 | ★ 核心 | 集中配置，`.env` → 强类型对象 | `settings` | — |
| `textproc.py` | 新增 | ★ 核心 | 归一化、jieba 分词、MATCH 构造、哈希 | `tokenize_index` / `tokenize_query` / `build_match` / `content_hash` | jieba |
| `db.py` | 修改 | ★ 核心 | 连接、DDL、触发器、自检、迁移入口 | `get_db_connection` / `init_db` / `check_schema` | — |
| `storage.py` | 修改 | ★ 核心 | 写入与取代（Append-Only + 乐观锁）、导出调度 | `insert_memory` / `supersede_memory` / `soft_delete` / `restore_entry` | version_chain / archive_manager / exporter |
| `ingest.py` | 修改 | ★ 核心 | 分块、LLM 提炼、清洗、去重、落库 | `extract_and_store` / `chunk_text` | textproc / storage / conflict_guard |
| `retriever.py` | 修改 | ★ 核心 | 三模式检索、打分、浮现、回写访问 | `retrieve_memories` / `get_active_surfaced` | textproc |
| `version_chain.py` | 新增 | ★ 核心 | 版本组创建、链展开、时间线组装 | `ensure_group` / `append_version` / `expand_chain` / `timeline` | — |
| `conflict_guard.py` | 新增 | ★ 核心 | 相似召回、LLM 判定、登记冲突 | `check_and_register` / `judge_relation` | textproc / llm |
| `archive_manager.py` | 新增 | ★ 核心 | 材料落盘、去重、取回、回收与瘦身 | `put_document` / `restore_span` / `reclaim_documents` | textproc |
| `decay.py` | 修改 | ★ 核心 | 权重衰减、软/硬归档、日志清理、对账 | `run_daily_maintenance` | archive_manager |
| `embedding.py` | 新增 | ○ 可选 | 文本向量化与 KNN 检索，双后端（本地 ONNX / 云端 API） | `embed(text)` / `search(vec, k)` / `upsert(entry)` | sqlite-vec / fastembed |
| `asr_adapter.py` | 新增 | ○ 可选 | 语音识别适配（本地/云端） | `transcribe(audio_path) -> [Segment]` | faster-whisper / HTTP |
| `media_ingest.py` | 新增 | ○ 可选 | 转码、冷存、ASR、转写分段入库 | `ingest_media` / `transcribe_only` | asr_adapter / archive_manager / ingest |
| `exporter.py` | 修改 | ○ 可选 | Obsidian `.md` 生成、异步 Git 推送 | `enqueue` / `flush` | — |
| `dashboard.py` | 修改 | ★ 核心 | HTTP API、鉴权、限流、静态托管 | `main` | 全部上层 |
| `mcp_server.py` | 修改 | ○ 可选 | MCP 工具注册与转发 | `main` | storage / retriever |
| `maintenance.py` | 新增 | ★ 核心 | CLI：cron 入口、对账、重建、诊断 | `python -m src.maintenance <cmd>` | decay / archive_manager / db |

### 6.6 ingest.py

写入链路里最容易被低估的一环：**分块决定模型一次能看到多少，归并决定散落的块能不能缝回一件事**。

#### 6.6.1 分块：结构优先、话题优先、字数兜底

2500 不是步长，是**目标值**。真正的规则是一个区间加一套切点优先级：

| 参数 | 默认 | 作用 |
|---|---|---|
| `CHUNK_MIN` | 800 | 低于此不单独成块，并入相邻块 |
| `CHUNK_TARGET` | 2500 | 期望长度 |
| `CHUNK_MAX` | 6000 | 硬上限，到顶必切 |
| `TOPIC_SIM_THRESHOLD` | 0.30 | 相邻段词袋 Jaccard 低于此值判“话题已变”，优先在此切 |

切点优先级：**标题行 > 空行（段落）> 句末标点 > 硬切**。

```python
# candidate_cuts(text) -> [(切点位置, 优先级)]，优先级 4=标题 3=空行 2=句末
# ⚠ 必须在循环外算一次：每块都重扫全文是 O(n²)，长文本会明显拖慢
def split_semantic(text: str) -> list[tuple[int, int]]:
    """返回 [(start, end)]，块长保证落在 [CHUNK_MIN, CHUNK_MAX] 内。"""
    text = normalize(text)
    if len(text) <= settings.chunk_max:
        return [(0, len(text))]

    chunks, start = [], 0
    while start < len(text):
        lo, hi = start + settings.chunk_min, start + settings.chunk_max
        window = [c for c in candidate_cuts(text) if lo <= c[0] <= hi]
        drift = [c for c in window
                 if topic_distance(text[start:c[0]], text[c[0]:c[0] + 600])
                 < settings.topic_sim_threshold]
        pool = drift or window
        if pool:
            cut = max(pool, key=lambda c: (c[1], -abs(c[0] - (start + settings.chunk_target))))[0]
        else:
            cut = min(len(text), hi)          # 无可用切点才硬切
        chunks.append((start, cut))
        start = cut
    return chunks
```

三条设计意图：

- **不在句子中间下刀**：句末标点是最后一道防线，硬切只在整段超长且无标点时发生；
- **同一话题跨过 2500 字不会被打断**：只要话题相似度仍高、切点优先级低，就一直延伸到 `CHUNK_MAX`（6000）才强制切；
- **`CHUNK_MIN` 防碎片**：每块都要一次 LLM 调用，碎片化会同时抬高成本与漏提率。

#### 6.6.2 滚动上下文：让第 N 块知道前 N-1 块说了什么

只靠 200 字原文重叠，救不了“跨 2000 字的延续”。因此提炼第 i 块时，把前序块已提炼的结论作为**只读上下文**传入：

```text
【本文档前序已提炼的结论（只读，勿重复提炼，仅用于理解指代）】
1. [decision] 部署方式定为 systemd
2. [knowledge] 日志集中在 /var/log/tinderbox
【本段正文】
……
```

第 2 块看到“那还是定 A 店吧”时，才知道前文在讨论选址。每块多 200～400 token，可忽略。

#### 6.6.3 提炼契约（新增三个字段）

```json
{
  "items": [
    {
      "category": "decision",
      "l1_summary": "首发城市定为成都，原因是本地试点成本最低。",
      "keywords": ["首发", "成都", "试点"],
      "confidence": "high",
      "importance": 0.8,
      "topic": "首发城市选择",
      "continues_previous": true,
      "topic_shift": false
    }
  ]
}
```

| 字段 | 用途 |
|---|---|
| `topic` | 8～16 字稳定话题名；同一件事在不同块里必须用**同一个** topic 字符串 |
| `continues_previous` | 本块开头是否承接上一块的话题 |
| `topic_shift` | 本块内部是否发生话题切换（用于拆条） |
| `context` | 仅当本条是该话题的**第一条**时输出：一句话交代“为什么会有这件事”（缘起、计划、约束）。其余条目必须留空 |

**什么样的 L1 算合格**（三个例子，从差到好）：

| 写法 | 例子 | 问题 |
|---|---|---|
| 只有结论 | “四月改口，换成大宗商 B。” | 三个月后没人记得为什么改，等于又丢了一次 |
| 截断原文 | “四月改口，换成大宗商 B。原因是 A 的供货不稳定，有过两次断货，而且 128…” | 依据被切掉，还带着无用的细节 |
| **结论 + 依据** | “改口换成大宗商 B——因为 A 供货不稳有过两次断货，且贵 32 元” | 可复述、可复用、可推翻 |

依据里只保留**能改变判断的那部分**：价格差、断货次数、管理成本。包装、口感、天气这类细节进 L0，不进 L1。

#### 6.6.6 纵向：链首必须带前因

上一节管的是**横向**——一条记忆凭什么成立；这一节管**纵向**——这件事为什么会发生。

版本链有个天然的断层：**v2 之后可以“相对上一版”理解，v1 没有上一版**。如果链首只写结论，整条链就悬在空中——你知道“改到创业园区”，却不知道当初为什么会有“首站”这回事。

以一份真实的项目记录为例，一条合格的链首应当能还原出四段：

| 段 | 内容 | 落在哪 |
|---|---|---|
| 前提 | 决定做一辆咖啡车，周末卖手冲 | `context` |
| 计划 | 第一站有三个候选，先去考察 | `l1_summary`（结论一） |
| 发现 | 止损线是日均 60 杯；一周实测只有 34 杯 | `l1_summary`（结论二的依据） |
| 结果 | 首站改到创业园区 | `l1_summary`（结论二） |

**只给链首填 `context`，不是省事，是分工**：后续版本若都重复背景，链会变成一堆复读；靠 `predecessor_id` 回溯反而是精确的。

**实现上的一个坑**（demo 实测）：按“信息密度”给段落打分排序，会系统性地丢掉铺垫——缘起、候选、约束这些段落信息量低，但缺了它们，结论就是孤证。所以提炼的排序只能用于**取舍条数**，不能用于**决定前因**；前因必须按原文位置取它之前的段落。

#### 6.6.4 归并：把散落的块缝回一件事

全部块提炼完后执行一次 reduce（**一份文档一次**，不是每块一次）：

```text
候选 [{topic, l1_summary, block_index, ...}]
  ├─ 1. 按 topic 分组（字符串归一化 + 相似度合并）
  ├─ 2. 组内按 block_index 排序
  ├─ 3. 单组多条 → 一次 LLM 调用做“同话题合并”
  │       · 互补 → 合成一条更完整的 L1
  │       · 演化（B 推翻 A）→ 保留两条，写 supersede 关系
  │       · 重复 → 只留信息量最大的一条
  └─ 4. 每组产出：一个 memory_group + 1~n 条 L1（含 predecessor 链）
```

这是“A→B→A 回环”能被缝回去的关键：**话题归属由 `topic` 决定，不由块决定**。

#### 6.6.5 容错与降级

| 环节 | 处理 |
|---|---|
| 提示词 | 固定 JSON 输出；列出 5 个 category 判定标准。`l1_summary` 必须写成**“做了什么决定——因为什么”**：只留结论会丢失可复用性，复述会议过程则浪费；要的是**依据**，不是流水账 |
| 温度 | `temperature=0`，`max_tokens=1200` |
| 清洗 | 正则剥代码围栏 → 取首个 `{`/`[` 到末个 `}`/`]` → `json.loads` |
| 回填 | 缺 `category`→`knowledge`；缺 `confidence`→`medium`；缺 `importance`→0.5；超长截断并标 `truncated` |
| 重试 | 指数退避 1s/2s/4s，仅对 429、5xx、超时；解析失败不重试，改降级 |
| 降级 | 三次失败后取该块首句 + 首 200 字作 L1，`confidence='low'`，日志标 `LLM_DEGRADED` |
| 去重 | 归并阶段按 `content_hash` + 话题相似度双重去重 |
| 幂等 | `(doc_id, chunk_index, topic)` 唯一：重跑覆盖不追加 |
| 块级失败 | 已入库的块不回滚；记 `L0_EXTRACT_FAIL`，续跑按 `chunk_index` 跳过已完成块 |

**规则提炼 vs LLM 提炼：同一份材料的实测**（demo，sample.txt，1,313 字，2026-10-26）

| 指标 | 规则提炼 | LLM 提炼 |
|---|---|---|
| 条数 | 22 | 16 |
| 带依据（出现“因为”） | **3/22 = 14%** | **15/16 = 94%** |
| 带前因（`context`） | 0/22 | 2/16 |
| 平均字数 | 48 | 49 |
| 摘要被截断 | 0 | 0 |
| 耗时 | 10 ms | 8,416 ms |

**同一段原文的两种产物**：

> 规则：`最后决定：首站放在大学城——因为学生对新东西接受度高，愿意为了拍照排队，试错成本`
>
> LLM：`首站选址定为大学城，设一个月窗口、日均60杯为止损线——因为学生接受度高、试错成本低`

规则版把“选址、窗口期、止损线”拆成三条才说完；LLM 版一条说完。**这正是判断“提炼质量”最直接的证据**：不是摘要更漂亮，而是**一条记忆装下了完整的判断**。

**对检索的连带影响**（这是容易忽略的）：

| 查询 | 规则版 top1 | LLM 版 top1 |
|---|---|---|
| 选址 | “最后决定：首站放在大学城…”（摘要里**没有**“选址”二字） | “首站**选址**定为大学城…” |

规则版的摘要不含标题词，只能靠 `keywords` 列命中，排序被 BM25 长度偏置带偏——这个坑在 LLM 版自己消失了。

#### 6.6.8 规则提炼：精确优先

规则提炼（LLM 不可用时的降级路径）有一个结构性缺陷：**它判断不了“值不值得记”**。原实现是“每块取分数最高的 N 条”——**相对排名，没有绝对标准**，于是再烂的句子也能挤进前 20。长文本一进来就失控：14,000 字的叙事文本产出 **175 条** L1，平均 80 字一条。

**分数其实分得开**（实测，2026-10-26）：

| 语料 | 最高分 | 中位分 |
|---|---|---|
| 业务材料（`sample.txt`，1,241 字） | **5.3** | 3.3 |
| 叙事文本《孔乙己》2,768 字 | 1.6 | 0.7 |
| 叙事文本《藥》4,813 字 | 1.7 | 0.5 |

业务材料分数集中在 3~5，叙事文本压在 0.5~1.7，**中间是空的**。一条绝对阈值就能把两类分开。

**三层策略**：

```text
① 绝对阈值 MIN_SCORE（业务材料实测 2.0）——低于它视为"没有可记的信号"
② 文档预算 = max(20, 字数/100)，封顶 60 —— 只作防爆上限
③ 兜底：整份都没信号时，保留最多 8 条并置 confidence='low'
```

**第 ③ 条不可省**：静默返回 0 条会让用户以为系统坏了。宁可给几条低置信的，也别给“什么都没有”。

| 语料 | 修前 | 修后 |
|---|---|---|
| 叙事文本四篇 | 175 条 | **32 条**（每篇 8 条，标 low） |
| 业务材料 | 22 条 | **20 条**（冲突与版本链不受影响） |

**这是有意的取舍：降级路径要精确优先。** 少了无非是漏记；多了会**污染检索与冲突配对**——垃圾记忆混进候选池，配对错一次，后面链条全错。

代价要说清：阈值把叙事文本里分数低的句子筛掉了，查「茴香豆」「长衫」在该语料中变为 0 条。**真要用小说、日记，走 LLM 路径**，它不会这么干。

**两个实现陷阱**（都踩过）：

1. **预算是上限，不能反过来当主筛选**——第一版把预算写成 `字数/400`，1,241 字的材料只给 3 条，冲突全检不出来；
2. **没有版本链时要判空**——检出 0 处冲突时下游 `max()` 空序列直接崩。

#### 6.6.7 可复现性：LLM 调用必须可重放

LLM 提炼有个隐蔽的问题：**同一份输入，两次运行产出不同**。实测同一份材料连跑三次，冲突数 1 / 0 / 0，版本链条数 4 / 3 / 2——下游全部跟着漂。

这不是准确率问题，是**可测性问题**：所有“跑一遍看看对不对”的验证方式全部失效。

**做法**：每次调用的原始输出按 `sha256(请求体)` 落盘，同一 prompt 第二次起直接读缓存。

```python
def chat(prompt: str, *, system="", temperature=0.0, max_tokens=1200) -> str:
    payload = {"model": MODEL, "messages": msgs,
               "temperature": temperature, "max_tokens": max_tokens}
    path = CACHE / (sha256(json.dumps(payload, sort_keys=True))[:16] + ".json")
    if path.exists():
        return json.loads(path.read_text())["text"]          # 重放
    data = post("/chat/completions", payload)
    path.write_text(json.dumps({"text": data["choices"][0]["message"]["content"],
                                "usage": data.get("usage"),
                                "created_at": now()}))       # 录制
    return data["choices"][0]["message"]["content"]
```

| 收益 | 实测 |
|---|---|
| 回归可复现 | 两次运行 122 行日志**逐行一致** |
| 省时间 | 21.5 s → **0.25 s** |
| 省费用 | 11 次请求 → 0 次 |
| 可审计 | 缓存里留有 prompt 摘要、模型、usage、时间 |

缓存目录只是“本地素材”，真实实现里它就是**提炼审计日志**的雏形——出了问题能回答“当时模型到底看到了什么、回了什么”。

#### 6.6.1 分块器的两条实现约束（都是踩过的坑）

**① 上限参数必须真正生效。**

demo 里 `split_semantic(text, target=700, hard_max=1100)` 的 `hard_max` 声明了却从未被使用——分块只按空行切。于是 5,216 字的《故鄉》被切成 **1 块**，整篇挤进同一个提炼窗口。

| | 修前 | 修后 |
|---|---|---|
| 《故鄉》5,216 字 | 1 块 | 6 块（最长 914 字） |
| 四篇小说合计 | 4 块 / 73 条 L1 | 18 块 / 175 条 L1 |

教训：**参数写了不等于生效**。上限类参数必须有一条断言——“任何块长度 ≤ hard_max”，在自测里跑。

**② 没有空行时，回退顺序不能反。**

原实现只认空行；而**粘贴的聊天记录、PDF 提取文本、绝大多数小说 txt 都没有空行**，直接退化成一块。正确的回退顺序：

```text
空行分段  →  单行分段  →  句末标点  →  硬切
```

反过来（先按句切）会切碎自然段落，把本该一起提炼的内容拆散。文档 6.6 的切点优先级（标题 > 空行 > 句末 > 硬切）本身是对的，**错在实现只做了第一级**。

#### 6.6.9 写入与增强必须分离

早期实现里，`ingest()` 直接调 LLM 提炼——结果是**写入路径依赖外部服务**：断网写不进去，接口慢 8～21 秒，超时还要重试。这违反了一条底线：**记忆的持久化不该把命交给别人**。

拆成两条路：

| 阶段 | 做什么 | 联网 | 耗时 | 失败影响 |
|---|---|---|---|---|
| **写入** | 落 L0 → 规则提炼 L1 → 入库（`extract_state='provisional'`） | **不需要** | 十几毫秒 | 无 |
| **精修** | LLM 把摘要改写成「结论——依据」，写 `memory_revisions` | 需要 | 每条一次调用 | 保持原样，不影响已有数据 |
| **向量** | 异步补（未实装） | 需要 | — | — |

**三条实现约束**：

1. **写入路径里不允许出现任何网络调用**——包括“探活”。探活失败就阻塞写入，是本末倒置。
2. **精修必须能拒绝劣化**。LLM 会把“项目最初的构想”改写成“第一站选大学城”，事实全丢。加一道闸：新摘要比原摘要短 40% 以上、或不含“——”结构，就拒收并保持原样。
3. **只精修“干净”条目**：已进版本链（`version_no > 1`）、有冲突、有关联关系的条目不碰——它们已被别的结构引用，改一个字段会牵连一片。

**实测**（`demo/run_offline.py`）：模拟断网 → 20 条 **15 ms** 落库、全部 `provisional`、检索照常；恢复联网后精修 8 条 → 采纳 7、**驳回 1**。

### 6.9 conflict_guard.py

#### 6.9.1 判定流程

```
新 L1 拟定
   │
   ├─ 1. 召回：按 tokenized_content 取 FTS 候选 top 5（同 user，status IN active/completed）
   │      向量路常态启用：memory_vectors KNN 取 top 5，与词法路按 entry_id 合并
   │
   ├─ 2. 相似度闸门：sim < 0.35 → 判为 unrelated，直接放行（不调 LLM，省费用）
   │      sim = 1 - normalized_bm25  （或 cosine，若走向量）
   │
   ├─ 3. LLM 判定：对每个候选单独判一次（候选通常 1～3 条，成本可控）
   │      输出 relation ∈ {unrelated, complement, override, duplicate}
   │
   ├─ 4. 动作：
   │      unrelated  → 放行
   │      complement → 放行，并给两条互加 related_group 提示（不建组）
   │      duplicate  → 放行但标 pending_merge（去重候选，等待合并）
   │      override   → confidence ≥ 0.80 才标 pending_merge（否则仅告警，避免误杀）
   │
   └─ 5. 登记：写 memory_conflicts + 条目 status='pending_merge'（同事务）
```

**为什么不自动 supersede**：LLM 误判“覆盖”会直接让有效记忆失效。因此 `override` 一律先进 `pending_merge`，由人（或 MCP 的 `resolve_conflict`）裁决。这是把“不可逆动作”从模型手里拿回来的关键设计。

#### 6.9.2 LLM 判定契约

系统提示（节选）：

```
你是记忆一致性判定器。给定两条记忆 A（既有）与 B（新），判断 B 与 A 的关系：
- unrelated   ：主题不同，可共存
- complement  ：同主题但补充细节，不否定 A
- override    ：B 明确推翻 A 的结论（如方案变更、数值修正、决定反转）
- duplicate   ：B 与 A 语义等价，仅措辞不同

只有在 B 明确表达"A 已过时/被替代"或"A 的结论为假"时才判 override。
仅"更详细""换角度"一律判 complement。
只输出 JSON，不要解释。
```

用户提示：

```
A: [{category}] {l1_summary}  (生效: {valid_from})
B: [{category}] {l1_summary}  (来源: {source})
```

输出：

```json
{
  "relation": "override",
  "confidence": 0.86,
  "reason": "B 将数据库从 MySQL 改判为 PostgreSQL，与 A 冲突",
  "merged_summary": "..."
}
```

校验：`relation` 不在枚举内 → 降级 `unrelated` 并记 `PARSE_FAIL`；`confidence` 缺失 → 0；`merged_summary` 仅在 `duplicate/override` 时有意义。

#### 6.9.3 候选召回：向量为主、FTS 兜底

旧做法只用 FTS 召回候选，字面不重合就漏——“换了说法”的冲突永远判不出来。v2.2 起改为双路：

| 路径 | 做法 | 覆盖 |
|---|---|---|
| 语义路（主） | `embedding(new_l1)` → `memory_vectors` KNN 取 top 5 | 换了说法、同义改写、跨块延续 |
| 词法路（兜底） | 原 FTS 召回 top 5 | 向量不可用、专有名词精确匹配 |

两路按 `entry_id` 合并去重后，相似度统一用 **cosine ∈ [0,1]**，闸门 `CONFLICT_SIM_GATE = 0.35` 不变（向量可用时不再走 BM25 归一化，两种分数不混用）。

**融合后的效果**：`override` 类冲突的召回率从“依赖字面重合”提升到“依赖语义”，这是把冲突治理从“能发现改了数字”扩展到“能发现换了说法”。

#### 6.9.4 三种关系的闸门不对称

同一个判定器，三种用法，闸门位置完全不同：

| 关系 | 后果 | 判错的代价 | 闸门 |
|---|---|---|---|
| `override` | 旧条目作废，转入 history | **不可逆** | 严：置信 ≥ 0.8，且**仍要人工裁决** |
| `duplicate` | 挂起等合并 | 可逆，但烦 | 中：置信 ≥ 0.8 直接挂起 |
| `complement` | 只多一条链接 | 推荐不准，无实质损失 | 松：同话题 + 无变更词 + 至少 1 个共同实词即可 |

一句话：**宁可多连，不可错杀。**

实测（2026-10-26，30 条既有 + 5 条补充）：5 条补充里认出 3 组互补，另外 2 条未连——`杯盖便宜 4 毛` 该连到“单杯成本 6 块 2”但共同实词太少；`太阳能板` 是全新话题，不连反而是对的。

#### 6.9.5 配对优先于判定

判定再准，配错对象也白搭。实测踩过三次：

| 现象 | 真实原因 |
|---|---|
| 「改口」配到「讨论过三个候选」 | 罗列段把地名复述一遍，字面重合最高 |
| 跨文档比 `l0_offset` | 偏移是文档内的坐标，跨文档比大小毫无意义 |
| 主项目被并入补充材料 | 按“自身条数”选根，而主项目自身 0 条（条目都在子项目上） |

三条都是同一个病：**判断依据选错了维度**。所以配对前先做一件事——**问这句话在干什么**：

| 言语行为 | 标志 | 能否当“前任” |
|---|---|---|
| `change` 改动 | 改口 / 改成 / 换成 / 推翻 / 搬到 / 定下来 | **能** |
| `decision` 拍板 | 决定 / 定了 / 定在 / 采用 | **能** |
| `survey` 罗列 | 讨论过 / 候选 / 考虑过 / 比较了 | **否**——它不下结论，无被取代的可能 |
| `note` 备注 | 其余 | 否 |

配对规则：

```text
候选前任 = 同文档 ∩ 行为 ∈ {change, decision}
得分     = 0.7 × 字面重合 + 0.3 × 同话题 (+0.06 若候选是组内现行版本)
```

最后那个 0.06 是“别挂在老尸首上”：链条应该长在当前版本上，而不是某个已被取代的旧节点。

**效果**：修正前，「改口」挂在“讨论三个候选”下面，真正的「决定」被孤立成另一条记忆；修正后链条正确成型 `v1 决定 → v2 改口`，检索时同组只出一条。

> 这条规则的代价是**依赖分类准确**。分类错了，配对照样错——只是错得更少。真正的解法仍是向量召回（把候选范围缩小到“确实在说同一件事”），分类只负责把明显不该配的排掉。

#### 6.9.6 两个判定器取并集

规则判定和 LLM 判定**性格不同**：规则版激进（宁可多挂起），LLM 版保守（倾向认为“还能共存”）。实测同一批数据，规则版检出 3 处覆盖，LLM 版只认 1 处。

**做法**：两边都跑，取最“重”的关系。

```python
SEVERITY = {"unrelated": 0, "complement": 1, "duplicate": 2, "override": 3}

rel, conf, reason = max(results, key=lambda x: (SEVERITY[x[0]], x[1]))
```

任一判定器认为“被覆盖”，就挂起等人裁决，理由里附上另一方的意见。

**为什么是并集而不是交集**：漏判的代价是**旧结论继续生效且无人知晓**，误判的代价只是**多点一次裁决**。这两个代价差一个量级，所以宁可多挂。

这与 6.9.4 的闸门原则是同一条：**不可逆的动作，从严**。

## 7 检索与排序

### 7.1 三种模式

| 模式 | 索引 | 返回范围 | 典型场景 |
|---|---|---|---|
| `active` | `memory_fts_active` | 仅当前有效记忆 | 默认检索、MCP `query_memories` |
| `history` | `memory_fts_history` | 仅 `superseded` / `archived` | “上次的方案是什么”“为什么改掉的” |
| `hybrid` | 两者各取 30 | 合并去重 | 用户不确定记忆是否已失效时的兜底 |

`include_archive=True` 时再并入 `memory_fts_archive`（硬归档条目，需显式开启，且有额外延迟）。

> **界面不暴露前两个模式**。`mode` 是 API 参数，界面只给「全部」与「演变」两个入口——让用户先判断“这条记忆还有效吗”再选模式，是把系统的活儿推给人。

### 7.2 打分公式

```
候选 = RRF( FTS_rank , Vector_rank )
score = W_rel × S_fuse + W_rec × S_rec + W_weight × S_weight

S_fuse   = 归一化后的 RRF 分：Σ 1 / (k + rank_i)，k = 60
S_rec    = 0.5 ^ (age_days / half_life)
S_weight = 条目权重（0~1）

默认权重：W_rel = 0.60, W_rec = 0.25, W_weight = 0.15（和 = 1.0）
```

**为什么用 RRF 而不是加权求和**：BM25 是无界负数、cosine 是 0~1，两者量纲不同，直接加权需要额外归一化，而归一化参数会随语料漂移。RRF 只用**排名**，天然免疫量纲问题，是混合检索的工业标准做法。

```python
def rrf(rows: list[dict], k: int = 60) -> list[dict]:
    """rows 含 fts_rank / vec_rank（缺失为 None），返回带 s_fuse 的结果。"""
    for r in rows:
        s = 0.0
        if r["fts_rank"] is not None:
            s += 1.0 / (k + r["fts_rank"])
        if r["vec_rank"] is not None:
            s += 1.0 / (k + r["vec_rank"])
        r["s_fuse"] = s
    top = max((r["s_fuse"] for r in rows), default=1.0) or 1.0
    for r in rows:
        r["s_fuse"] /= top                     # 归一到 0~1，便于与其余两项相加
    return rows
```

**单路可用时**：只有 FTS（向量降级）时，`S_fuse` 退化为 FTS 的内部归一化排名；只有向量时同理。**不因某一路缺失而整体失效**。

**分类半衰期**（`S_rec` 用）：

| 类别 | `half_life`（天） | 理由 |
|---|---|---|
| `task` | 30 | 任务时效性强 |
| `decision` | 365 | 决策长期有效 |
| `knowledge` | 180 | 知识缓慢过时 |
| `preference` | 365 | 偏好稳定 |
| `fiction_inspiration` | 730 | 灵感几乎不失效 |

## 8 衰减、归档与 TTL 管道

### 8.1 管道全景

每日 03:00 由 cron / systemd timer 触发一次，七步串行。任一步失败只记告警并继续后续步骤（避免一步失败导致整轮停摆），结束后汇总一条报告：

| 步骤 | 动作 | 触发条件 | 结果 |
|---|---|---|---|
| 1 | 权重衰减 | `status IN ('active','completed')` 且 `pin=0 AND anchor=0` | `weight ×= m_eff`，下限 0.01 |
| 2 | 软归档 | `weight ≤ 0.10` | `status='archived'`，FTS 移入 history |
| 3 | 硬归档 | `status='archived'` 且 `weight ≤ 0.05` 且闲置 ≥ 180 天 | 搬入 `memory_entries_archive`，删除主表行 |
| 4 | 材料补齐 | `doc_id IS NULL` 但仍有遗留原文 | `put_document()` 后回填 `doc_id` 与区间 |
| 5 | TTL 清理 | `expires_at < now − 7 天宽限期` | 移回收站 → 物理删除，写 `L0_PURGE` |
| 6 | 日志清理 | `ts` 超出分级保留期 | 删除高频日志，语义日志压为月汇总 |
| 7 | 孤儿对账 | 每日一次 | DB ↔ 磁盘 ↔ FTS 双向修复或告警 |

顺序不可交换：**先衰减再归档**（否则当日权重变化要等次日才生效）、**先归档再清理**（归档条目不参与 TTL 清理）、**最后对账**（把前六步的残留统一兜住）。

### 8.2 三类生命周期的区别

| 对象 | 触发 | 主库变化 | 文件系统变化 | 可逆 |
|---|---|---|---|---|
| 记忆条目（软归档） | 权重低 | `status='archived'` | 无 | 是 |
| 记忆条目（硬归档） | 权重极低 + 长期未访问 | 搬入 `memory_entries_archive` | 无 | 半（可人工导回） |
| L0 原文 | TTL 到期 | `l0_state='purged'` | 回收站 → 删除 | 宽限期内是 |
| 音频 | TTL 到期 | `memory_media` 行置失效 | 回收站 → 删除 | 宽限期内是 |
| Blob | 引用归零 | `state='purged'` | 删除 | 否 |

**关键区分**：条目归档**不动文件**（L0 还在，仍可恢复原文）；L0 清理**不动条目**（摘要还在，只是无法再取原文）。两者独立，避免“条目一归档就丢原文”。

### 8.3 TTL 参数

| 对象 | 默认 TTL | 配置项 | 说明 |
|---|---|---|---|
| L0 · 未验证记忆 | 730 天 | `DOC_TTL_UNVERIFIED_DAYS` | 摘要从未被核对，原文是唯一依据，留得久 |
| L0 · 已验证记忆 | 180 天 | `DOC_TTL_VERIFIED_DAYS` | 摘要已被人确认/置顶/裁决，证据价值下降，可提前释放 |
| 音频 | 180 天 | `AUDIO_TTL_DAYS` | 体积最大，最短；转写文本另存为一份 L0 |
| 转写全文 | 365 天 | `TRANSCRIPT_TTL_DAYS` | 与 L0 同寿（它本身就是一份 L0） |
| 冷归档条目 | 3 年 | `ARCHIVE_EXPORT_YEARS` | 到期导出为文件、从库里裁掉（见 8.4） |
| 回收站 | 7 天 | `TRASH_GRACE_DAYS` | 二次确认窗口 |
| 孤儿 Blob | 7 天 | `TTL_ORPHAN_GRACE_DAYS` | 引用归零后的缓冲 |

**续期规则**：`restore_span` 只更新 `last_restored_at`，**不延长 TTL**。v2.0 写的“用过就续期”已取消——一份材料只被读过一次就永久占位，是存储失控的隐性来源。真要长期保留，用 `pin` 显式表达。

**分档的判据是“是否被核对过”，不是“旧不旧”。**

| 记忆状态 | 原文的价值 | 保留期 |
|---|---|---|
| 被编辑 / 置顶 / 冲突裁决确认过（`verified_at` 非空） | 低——摘要已经可信 | 180 天 |
| 纯 LLM 自动提炼、从未核对 | **最高——原文是唯一的纠错依据** | 730 天 |
| `pin` / `anchor` | — | 永不清理 |

判定顺序：`pin/anchor` > 已验证档 > 未验证档。三个值都在配置里，机构可以整套调成自己的合规期限（例如“一律 90 天”），只需把两个档位设成同一个数。

**一个刻意的不对称**：已验证档（180 天）比知识类记忆的软归档时点（≈229 天）还早——也就是说，一条已被确认的记忆，可能在它还没沉下去时原文就消失了。这是有意为之：**可信的是摘要，不是原文**；而未被确认的记忆恰恰相反，那时删原文等于销毁唯一的反悔机会。

**三种“别删”不是一回事**，混在一起，策略就失去意义：

| 机制 | 表达什么 | 谁决定 | 效果 |
|---|---|---|---|
| 置顶 `pin` | 用户优先级：待办、重要、稍后再看 | 用户随时改 | 排序靠前；原文豁免清理 |
| 锚定 `anchor` | 长期事实，不该随时间衰减 | 用户显式声明 | 豁免衰减与清理 |
| 已核对 `verified_at` | **这条摘要是可信的** | 人核对后显式打标 | 原文可提前释放（180 天） |

前两个是**组织方式**，第三个是**质量判断**。置顶一条待办，不等于确认了它的内容；核对过的记忆也不必置顶。因此 `verified_at` 只接受三种来源：

| `verified_reason` | 触发 | 含义 |
|---|---|---|
| `authored` | 人直接写入（`/api/add` 或 MCP `store_memory`，而非 LLM 提炼） | 摘要本身就是人的表述，不存在提炼失真 |
| `adjudicated` | 冲突裁决中被确认为有效 | 人看过两方内容后选了它 |
| `reviewed` | 看板上点「我核对过了」 | 逐条复核 |

**取消置顶后，原文回到它本来的档期**（已验证 180 / 未验证 730），不是从取消那一刻重新计时——置顶只是临时扣住，不改账。

## 9 HTTP API 规范

### 9.1 通用约定

| 项目 | 约定 |
|---|---|
| Base URL | `http://127.0.0.1:8765`（默认仅本机）；VPS 部署经反向代理暴露 HTTPS |
| 版本 | 路径不带版本号，靠 `X-API-Version: 2` 请求头协商；破坏性变更时改 `/api/v2/*` |
| 编码 | 请求/响应一律 `application/json; charset=utf-8`（上传接口除外） |
| 时间 | 全部 ISO-8601 UTC，精确到毫秒，形如 `2026-10-25T09:57:01.234Z` |
| 分页 | 游标分页：`?cursor=<opaque>&limit=20`，响应 `next_cursor` 为 `null` 表示结束 |
| 幂等 | 写接口支持 `Idempotency-Key` 头，24 小时内相同 key 返回首次结果 |
| 鉴权 | `Authorization: Bearer <API_TOKEN>`；未配置 token 时仅接受回环地址 |
| 追踪 | 每个响应含 `X-Request-Id`（UUID），日志按此关联 |

**统一响应包**

```json
{
  "ok": true,
  "data": {},
  "meta": { "request_id": "…", "elapsed_ms": 12, "mode": "active", "total": 3 },
  "error": null
}
```

失败时：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "STALE_VERSION",
    "message": "版本已变化，请重新读取",
    "detail": {"expected": 2, "actual": 3}
  }
}
```

### 9.2 错误码

| HTTP | `code` | 含义 | 客户端应做 |
|---|---|---|---|
| 400 | `INVALID_ARGUMENT` | 参数缺失/格式错 | 修正后重试 |
| 401 | `UNAUTHORIZED` | token 缺失或错误 | 补 token |
| 403 | `FORBIDDEN` | 越权访问他人 `user_id` | 不允许重试 |
| 404 | `NOT_FOUND` | 条目/媒体/冲突不存在 | 检查 ID |
| 409 | `STALE_VERSION` | 乐观锁失败（并发 supersede） | 重读最新版本后重试 |
| 409 | `ALREADY_SUPERSEDED` | 该条目已被取代 | 走 `restore` 或读新版本 |
| 409 | `CONFLICT_OPEN` | 同组存在未裁决冲突 | 先裁决 |
| 413 | `PAYLOAD_TOO_LARGE` | 超过 `upload_max_mb` | 压缩或分段 |
| 415 | `UNSUPPORTED_MEDIA` | MIME 不在白名单 | 转码后重传 |
| 422 | `EMPTY_L1` / `L1_TOO_LONG` | 内容不合法 | 修正内容 |
| 429 | `RATE_LIMITED` | 触发限流 | 退避重试（带 `Retry-After`） |
| 500 | `INTERNAL` | 未预期异常 | 报 `X-Request-Id` |
| 507 | `DISK_FULL` | 冷存储或库所在分区空间不足 | 清理后重试；不得半写 |
| 503 | `LLM_UNAVAILABLE` | 上游模型不可用（已降级则返回 200 + `degraded:true`） | 稍后重试 |

### 9.3 读接口

| 方法 | 路径 | 参数 | 说明 |
|---|---|---|---|
| GET | `/api/all` | `user_id`、`status=active\|completed\|pending_merge\|archived\|superseded`（默认 `active`）、`category`、`cursor`、`limit` | 列表。**默认只返回 `active`**（S1 返回“所有活跃记忆”，S2 明确默认口径） |
| GET | `/api/search` | `q`（必填）、`mode=active\|history\|hybrid`、`include_archive=0\|1`、`source`、`media=0\|1`、`top_k`、`group_dedup` | 三模式检索，返回 `score` 与 `matched_mode` |
| GET | `/api/detail` | `id` | 返回条目全字段 + 版本链 + L0 状态 + 媒体信息 + TTL 剩余 |
| GET | `/api/stats` | `user_id`、`range=7d\|30d\|all` | 统计：条目数、分类分布、归档率、冲突数、Token 节省、冷归档体积 |
| GET | `/api/dashboard` | `user_id` | 仪表盘聚合（统计 + 最近 10 条 + 待处理冲突数） |
| GET | `/api/archived` | `user_id`、`cursor` | 软归档列表（`status='archived'`） |
| GET | `/api/conflicts` | `user_id`、`state=open\|resolved\|ignored` | 冲突列表，含相似度、LLM 判定、置信度、建议动作 |
| GET | `/api/history/{group_id}` | — | 版本链时间线（`timeline()`） |
| GET | `/api/archive/l0` | `user_id`、`expires_before`、`cursor` | 冷归档列表与 TTL 剩余 |
| GET | `/api/media/{media_id}` | `sig`、`exp` | 媒体元数据；带签名时返回可回放地址 |
| GET | `/healthz` | — | 存活探针：`{ok, db, fts, disk_free_gb}` |
| GET | `/metrics` | — | 轻量指标（JSON）：QPS、p95、队列长度、blob 总量 |

**`/api/search` 响应示例**

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "entry_id": "mem-9f2c1a7b3d40",
        "l1_summary": "部署方式定为 systemd，不再使用 nohup。",
        "category": "decision",
        "status": "active",
        "score": 0.874,
        "rel": 1.0, "rec": 0.83, "weight": 0.72,
        "group_id": "g-7f3a2b11c9de",
        "version_no": 3,
        "predecessor_id": "mem-b2…", "superseded_by": null,
        "l0_state": "cold",
        "media_id": null,
        "created_at": "2026-10-20T02:11:09.512Z",
        "valid_from": "2026-10-20", "valid_to": null,
        "matched_mode": "active",
        "siblings": [
          {"entry_id": "mem-a1…", "version_no": 1, "status": "superseded"},
          {"entry_id": "mem-b2…", "version_no": 2, "status": "superseded"}
        ]
      }
    ],
    "total": 1
  },
  "meta": {"request_id": "1f0c…", "elapsed_ms": 11, "mode": "active", "degraded": false},
  "error": null
}
```

### 9.4 写接口

| 方法 | 路径 | Body 关键字段 | 说明 |
|---|---|---|---|
| POST | `/api/add` | **摘要须满足「结论 + 依据」**（缺依据返回 422 并提示补一句）；`user_id, content, category, confidence?, source?, media_id?, valid_from?, valid_to?, importance?` | 直接写入（不调 LLM），走 `insert_memory`；`source` 默认 `api` |
| POST | `/api/extract` | `user_id, text, source?` | 长文本 → 分块 → LLM 提炼 → 批量入库，返回条目列表 |
| POST | `/api/supersede` | `old_entry_id, new_content, new_category?, new_confidence?, expected_version_no?` | 事务化取代；`expected_version_no` 提供时启用乐观锁 |
| POST | `/api/restore` | `entry_id` | 软归档 → `active`；若同组已有 active，则先建冲突 |
| POST | `/api/pin` | `entry_id, pinned=true\|false` | 置顶开关 |
| POST | `/api/anchor` | `entry_id, anchored=true\|false` | 锚定开关（豁免衰减与 TTL） |
| POST | `/api/verify` | `entry_id, by, reason=authored\|adjudicated\|reviewed` | 显式标记摘要已被核对，把所属 L0 切到 180 天档；置顶**不会**自动触发 |
| POST | `/api/complete` | `entry_id` | 任务完成 |
| POST | `/api/conflicts/resolve` | `conflict_id, resolution=supersede\|merge\|keep_both\|ignore, merged_summary?` | 人工裁决 `pending_merge` |
| POST | `/api/l0/restore` | `entry_id, before?, after?` | 按条目区间取回原文，返回 `{text, offset, length, context}`；不落盘（详见 6.10.2） |
| POST | `/api/l0/purge` | `entry_id, dry_run?` | 移回收站或彻底删除 |
| POST | `/api/upload_recording` | `multipart/form-data`: `file, user_id, media_type?, transcribe=true\|false, group_id?` | 上传音频，触发 `media_ingest` |
| POST | `/api/transcribe` | `media_id` 或直接上传 | 仅转写，**不写入记忆库**（供人工校对） |

**`/api/supersede` 响应**

```json
{"ok": true, "data": {"entry_id": "mem-c3d4e5f6078a", "version_no": 4,
                      "superseded": "mem-9f2c1a7b3d40", "group_id": "g-7f3a2b11c9de"},
 "error": null}
```

**`/api/conflicts/resolve` 语义**

| `resolution` | 效果 |
|---|---|
| `supersede` | 新条目取代旧条目（走 `supersede_memory`），旧条目 `superseded` |
| `merge` | 用 `merged_summary` 取代两者，旧两条均 `superseded`，`memory_groups.merged_into` 指向目标组 |
| `keep_both` | 两条均置 `active`，冲突置 `resolved`，`memory_conflicts.resolution='keep_both'` |
| `ignore` | 新条目保留 `active`，冲突置 `ignored`（表示“审过了，不是冲突”） |

### 9.5 鉴权与签名

**Token 鉴权**（服务端）

```python
def _require_token(self):
    if settings.api_token:
        got = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(got, settings.api_token):
            raise ApiError(401, "UNAUTHORIZED")
    else:
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            raise ApiError(401, "UNAUTHORIZED")
```

**媒体签名地址**（不暴露冷存储路径）

```
GET /api/media/{media_id}?exp=1761700000&sig=HMAC_SHA256(media_id + exp, SIGN_SECRET)

服务端校验：exp 未过期 且 hmac.compare_digest(sig, 重算值)
通过后：以流式响应转发文件内容，Content-Disposition: inline
```

**CORS 策略**

| 场景 | 允许来源 | 说明 |
|---|---|---|
| 看板由 `dashboard.py` 托管（推荐） | 同源 | 无需 CORS 头，最简单也最安全 |
| 看板以 `file://` 打开 | `Origin: null` | 需显式允许 `null`，等同于“任何本地文件都能访问”，**不推荐** |
| 其他前端 | 配置白名单 | `CORS_ALLOW_ORIGINS=https://foo.example` |

> S1 的做法是“双击 `dashboard_v2.html` 直接打开”，S2 要求“前端 `fetch` 加 token、服务端加 CORS”。两者叠加会撞上 `Origin: null` 的安全陷阱。本方案改为**由 API 进程同源托管看板**（`GET /` 返回 HTML），既满足“双击即用”的体验（打开浏览器书签即可），又不必开放 `null` 来源。

### 9.6 限流

| 接口组 | 限制 | 维度 |
|---|---|---|
| 读接口 | 120 次/分钟 | 每 token |
| 写接口 | 30 次/分钟 | 每 token |
| `/api/extract` | 10 次/分钟 | 每 token（涉及 LLM 费用） |
| `/api/upload_recording` | 5 次/分钟，串行转写 | 每 token |

实现：进程内令牌桶（`dict[str, deque]`），单机足够；多进程部署时改用 SQLite 计数表。

## 11 Web 看板

### 11.1 页面结构

| # | 页面 | 核心内容 | 依赖接口 |
|---|---|---|---|
| 1 | 搜索 | **一次给全**（现行 + 历史），旧版本划掉并标灰；卡片含分数与日期 | `/api/search?mode=hybrid` |
| 2 | **演变** | 版本链时间轴：`v1→vN` 横排，节点标状态与**间隔天数**；点任一步看该版原文 | `/api/chains`、`/api/entry` |
| 3 | **星网** | 按项目分列的折叠看板：项目列 → 话题分组 → 记忆条目，每条带类别 tag，可按 tag 全局筛选 | `/api/concepts`、`/api/concept` |
| 4 | 冲突裁决（见 11.4） | `pending_merge` 列表：判定理由、置信度、三个按钮（取代 / 两条都留 / 忽略） | `/api/conflicts`、`/api/conflicts/resolve` |
| 5 | 详情弹窗 | 全字段 + 版本链 + **前因** + 相关记忆 + L0 原文片段 + 操作（置顶 / 锚定 / 恢复） | `/api/detail`、`/api/history/{gid}` |

**非必要页面（按需再开，不进主计划）**：仪表盘、全部列表、手动添加、音频、冷归档、统计。这 6 个不阻塞任何核心链路——先不做，等真有人天天用再说。

### 11.2 交互规范

**失效记忆的呈现**（S2 要求“删除线、灰化，点击沿 `superseded_by` 跳最新”）

```html
<tr class="row-superseded" data-entry-id="mem-a1…" data-superseded-by="mem-c3…">
  <td class="l1"><s>旧结论：使用 nohup 启动</s></td>
  <td><span class="badge badge-superseded">v1 已被取代</span></td>
  <td><a href="#" data-nav="entry" data-target="mem-c3…">查看最新 v3 →</a></td>
</tr>
```

- 状态徽标：`active`(绿) / `completed`(蓝) / `pending_merge`(橙) / `archived`(灰) / `superseded`(灰+删除线)；
- **视图分工**：搜索一次给全，旧版本直接划掉——用户不该先判断“这条还有效吗”再去选模式；要看“这件事怎么变的”去「演变」，要看“有哪些项目”去「星网」。**模式是 API 的能力（7.1），不是界面的必答项**；
- **星网三层折叠**：项目列 → 话题分组 → 记忆条目。列与分组**默认收起**，只显示名称与条数，避免一整条长列表；顶部一排类别 tag 做全局筛选（decision / task / knowledge / preference）；
- **间隔天数即信号**：版本链上两个节点之间标 `+N 天`——改得越密说明决策还没定下来，改得越疏说明在收敛。
- **组织标记与质量标记分开显示**：置顶用图钉图标、锚定用锚图标，**已核对**用独立的文字徽标「已核对」。两者视觉上必须可区分——否则用户会以为置了顶就等于确认过内容；
- 点击失效行的任意位置 → 沿 `superseded_by` 逐级跳到链尾，并在详情弹窗顶部提示“这是第 N 版的历史，最新版是 vM”；
- 历史模式检索结果的分数旁标注 `matched_mode`，避免用户误以为旧结论仍有效。

**事件委托**（沿用 S1 的正确做法，禁止 inline `onclick`）

```javascript
document.addEventListener('click', (e) => {
  const nav = e.target.closest('[data-nav]');
  if (nav) {
    e.preventDefault();
    const { nav: kind, target } = nav.dataset;
    if (kind === 'entry') openDetail(target);
    if (kind === 'group') openHistory(target);
  }
});
```

**API 客户端**（统一注入 token 与错误处理）

```javascript
const API = {
  token: localStorage.getItem('mv_token') || '',
  async call(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      headers: { 'Content-Type': 'application/json',
                 ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
                 ...(opts.headers || {}) },
    });
    const body = await res.json();
    if (!body.ok) {
      toast(`${body.error.code}: ${body.error.message}`, 'error');
      if (res.status === 409) refreshCurrentView();
      throw new Error(body.error.code);
    }
    return body.data;
  },
};
```

## 16 测试与验收

### 16.1 测试矩阵

| ID | 类型 | 用例 | 方法 | 通过标准 |
|---|---|---|---|---|
| T1 | 单元 | 分词与归一化 | 固定 50 条中英混排样本 | 全角/半角、大小写、标点不影响 token 集合 |
| T2 | 单元 | `build_match` 抗注入 | 输入 `a" OR "b`、`*`、`NEAR(` | 不抛异常，生成的表达式只含引号包裹的 token |
| T3 | 集成 | 写入 → 检索闭环 | 写入 100 条，检索关键词 | top 1 命中率 100% |
| T4 | 集成 | **中文召回率对比** | 200 条查询集，分别用 v1(unicode61) 与 v2(jieba) | Recall@10 ≥ 0.85，且比 v1 高 ≥ 15 个百分点 |
| T5 | 集成 | **并发 supersede 一致性** | 8 线程同时对同一条 supersede | 仅 1 个成功，其余抛 `STALE_VERSION`；链完整无分叉 |
| T6 | 集成 | **冲突 Guard 精确率** | **≥ 300 对**人工标注样本（无关/补充/覆盖），按类别分层抽样 | 自动挂起部分精确率 ≥ 0.85；`override` 误判率 ≤ 0.10；**召回率单列**（并集机制下以召回换精确，两者不可混算） |
| T7 | 集成 | **历史追问跨状态召回** | 构造 v1→v5 链，`mode=history` 查 v2 独有词 | 能召回 v2；`mode=active` 不召回 |
| T8 | 集成 | **L0 归档/恢复/TTL** | 写入 → 归档 → 恢复 → 改 TTL 为过去 → 清理 | 恢复内容与原文字节一致；清理后 `l0_state='purged'`，回收站有文件 |
| T9 | 集成 | **音频端到端** | 上传 3 分钟 wav → 转写 → 入库 → 检索 → 回放 | 端到端 < 90 s（small 模型）；检索命中；回放 200 |
| T10 | 集成 | 幂等 | 同内容写 3 次 | 只产生 1 条；第 2、3 次返回 `deduped=true` |
| T11 | 集成 | 去重与 refcount | 同音频上传 3 次后删 2 次 | 物理文件仅 1 份；`ref_count` 与引用数一致 |
| T12 | 集成 | 迁移幂等 | 对 v1 库跑 2 次 migrate | 第 2 次为 no-op（检测到已 2.0.0）；行数不变 |
| T13 | 性能 | 检索延迟 | 10 万条造数，1000 次随机查询；分冷/热两种 | 混合：冷 p95 ≤ 300 ms、缓存命中 p95 ≤ 120 ms；纯 FTS 降级 p95 ≤ 150 ms |
| T14 | 性能 | 写入吞吐 | 单线程连续 1000 次 `insert_memory` | ≥ 200 条/秒（不含 LLM） |
| T15 | 故障 | LLM 不可用 | mock 全部超时 | 降级为规则提炼，写入成功，`degraded=true` |
| T16 | 故障 | 磁盘写满 | 用 `fallocate` 占满分区后写入 | 返回 507/`DISK_FULL`，不产生半条记录 |
| T17 | 故障 | 进程中途 kill | 写入事务执行中 `kill -9` | 重启后无脏数据（WAL 回滚），无重复 version_no |
| T18 | 安全 | 未授权访问 | 无 token 访问非回环地址 | 401；`bind_host=0.0.0.0` 且 token 为空时拒绝启动 |
| T19 | 集成 | **跨块话题延续** | 造 5 000 字“话题 A→B→A”的文本 | A 的两段落进同一版本组；不产生互相矛盾的 L1；块数 ≤ 4 |
| T20 | 集成 | **L0 回收与瘦身** | 100 条 L1 共享 1 份 L0，删至剩 1 条 | `live_ref_count` 降到 1；满 180 天后触发瘦身；瘦身后区间仍可读 |
| T21 | 集成 | **长文档 L0 唯一性** | 导入 5 万字文档 | 只产生 1 份 `memory_documents`、1 个 blob；N 条 L1 的 offset 递增且不重叠 |
| T22 | 集成 | **混合召回提升** | 200 条查询集，分别跑纯 FTS 与 FTS⊕向量 | Recall@10 从 ≥0.85 提升到 ≥0.90；同义改写类查询提升 ≥10 个百分点 |
| T23 | 故障 | **向量不可用降级** | 卸载 sqlite-vec 后重启 | 检索仍返回结果，`degraded="vector_unavailable"`，耗时 ≤ 纯 FTS 的 1.2 倍 |
| T24 | 集成 | **分档保留** | 三份同长度 L0：A 全部 `mark_verified`、B 从未核对、C 只被 `set_pin` | A 在 180 天回收；B 撑到 730 天；C 因置顶被扣住、取消置顶后按未验证档处理；三者在回收前 `l0_state` 均为 `live` |
| T25 | 单元 | **置顶不得写验证位** | 对未核对条目调用 `set_pin(1)` 再查 `verified_at` | 保持 `NULL`；`verified_reason` 不接受 `pinned` |
| T26 | 集成 | **概念挂靠精度** | 100 条人工标注归属的记忆，跑挂靠 | precision ≥ 0.95 且 coverage ≥ 0.60；margin 闸门用 6.15.2 的标定值 |
| T27 | 集成 | **补充记忆不触碰原有记录** | 灌入 5 条纯补充材料，前后逐条快照比对 | 原有条目状态/版本/摘要改动 0 条；冲突数不增；关系数 > 0；新词可检索 |
| T28 | 集成 | **LLM 提炼可复现** | 同一输入连跑两次 | 日志逐行一致；缓存命中率 100%；无缓存时允许差异但需记录 |
| T29 | 单元 | **分块上限生效** | 5,000 字无空行文本 | 每块 ≤ `hard_max`；块数 > 1 |
| T30 | 集成 | **简繁检索互通** | 繁体材料 + 简体查询 | 命中数与简体材料一致；反过来也成立 |
| T31 | 集成 | **断网可写入** | 模拟 LLM 不可用，灌 1 份材料 | 全部条目 `provisional`；检索可用；写入 < 100 ms |
| T32 | 集成 | **精修不劣化** | 对 8 条跑精修 | 采纳的含「——」；被驳回的原样保留；`memory_revisions` 有记录 |
| T33 | 集成 | **浮现不重复** | 同话题 3 条，取 top3 | 同话题只出现 1 条；每条带 `why` |
| T34 | 集成 | **Markdown 往返** | 导出 → 人工改一行 → 重建 | 改动能被检索到；条数一致 |

## 17 实施路线

### 17.1 阶段划分

| 阶段 | 目标 | 交付物 | 估时 | 前置 |
|---|---|---|---|---|
| **P0 正确地记住** | 结构立住，中文可检 | 新 Schema + 双 FTS + 分词 + 事务化 supersede + ingest（分块/提炼/归并）+ retriever + 鉴权 | **10 天** | — |
| **P1 记得有分寸** | 生命周期与冲突可控 | conflict_guard + version_chain + archive_manager + 检索三因子 + L0 压缩 + TTL + 概念层 | 11 天 | P0 |
| **P2 看得清** | 人可审阅 | 搜索 / 演变 / 星网 / 冲突裁决 / 详情，5 个页面 | 4 天 | P1 |

**核心合计 ≈ 30 人日**（P0 10 + P1 13 + P2 5 + 2 缓冲），单人约 6 周。

> **估时口径**：以上是**在已有 demo 代码基础上**的估算。若从零实现（没有 `tb.py` 那 1,900 行可参考），`ingest`（分块/提炼/归并）与数据迁移（版本组重建、材料归并）都是硬活，**按 35～40 人日估**。v2.16 写的 21 人日偏乐观。

**非必要功能（不进主计划，按需启动）**：

| 功能 | 估时 | 前置 | 什么时候才做 |
|---|---|---|---|
| 音频：上传 / ASR / 回放 | 7 天 | P1 | 真的开始用录音记事了 |
| Obsidian 导出 + Git | 2 天 | P0 | 想在 Obsidian 里读这些记忆 |
| 数据迁移 v1 → v2 | 2 天 | P0 | **只有 v1 真在生产跑过才需要** |

**已砍掉**：多用户隔离、向量压缩（PQ/BIT）、11 页看板、向量检索进 P1。理由见附录 D.18。

### 17.5 实现进度（截至 2026-10-27）

按“demo 里真跑通”作为唯一标准：

| 能力 | 文档位置 | 状态 |
|---|---|---|
| Schema / 双 FTS / 触发器 | 5.x | ✅ 跑通 |
| L0 落盘与按需取回（span） | 6.10 | ✅ 跑通 |
| 分块 + L1 提炼 | 6.6 | ✅ **规则写入 + LLM 精修**（不再是两条并列路径） |
| 三因子检索 + hybrid 一次给全 | 7.2 | ✅ 跑通 |
| 版本链 + 事务化 supersede | 6.8 | ✅ 跑通 |
| 冲突检测（规则 / LLM / 并集） | 6.9 | ✅ 跑通 |
| **人工裁决（看板）** | 11.3 | ✅ 跑通 |
| **离线写入 + 异步精修** | 6.6.9 | ✅ 跑通（断网 15 ms 落库） |
| **对话开头主动浮现** | 7.4 | ✅ 已接看板（顶部常驻面板，带理由） |
| **Markdown 镜像** | 5.22 | ✅ 单向导出 + 可从 md 重建 |
| 概念层（星网） | 5.19 / 6.15 | ✅ 结构跑通；自动挂靠精度不达标，靠人搭骨架 |
| 互补关系 | 5.20 | ✅ 跑通 |
| **衰减 / 硬归档 / TTL 回收** | 8.x | ✅ 跑通（dry-run 默认；分档与幂等都验过） |
| **维护 CLI（cron 入口）** | 6.14 | ✅ `maintenance.py stats/decay/reclaim/check` |
| **API 鉴权 / 限流** | 9.x | ✅ 令牌 + cookie + 限流 + 无 CORS（10 项测试通过） |
| 评估集与指标 | 16.2 | ✅ 冒烟级（23 条 / 10 对）；**不足以当验收** |
| 音频 / Obsidian 导出 / 数据迁移 | — | 非必要，未做 |
| 向量检索 | 5.18 | 非必要；30 条实测未证明收益 |

**三块 ❌ 都在 P0/P1 的交付物里**，不是锦上添花：没有衰减回收，L0 会无限增长；没有维护 CLI，回收只能手工触发；没有鉴权，看板只能绑在 127.0.0.1。

> **一个必须直说的信号**：文档已到 v2.21（19 章 + 22 节修订史），而这三块核心一个字没写。**文档完备性领先于实现完备性，是危险信号，不是成就感。** 在本表出现三个 ✅ 之前，不应再扩写设计章节——写文档的时间若超过写代码的时间，说明在逃避难的 part。

## 附录 A 配置项全表

| 变量 | 默认 | 说明 |
|---|---|---|
| `DB_PATH` | `memory.db` | 主库路径 |
| `ARCHIVE_ROOT` | `archive` | 冷存储根目录 |
| `VAULT_PATH` | `vault` | Obsidian 仓库路径 |
| `BIND_HOST` | `127.0.0.1` | 监听地址；非回环时强制要求 token |
| `BIND_PORT` | `8765` | 端口 |
| `API_TOKEN` | 空 | Bearer token；为空时仅允许本机 |
| `SIGN_SECRET` | 空 | 媒体签名密钥；为空时禁止签发回放地址 |
| `DEEPSEEK_API_KEY` | — | LLM 密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 兼容端点 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `LLM_DISABLE` | `false` | `true` 时退化为规则提炼（不发外网） |
| `L1_MAX_CHARS` | `400` | L1 摘要长度上限 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `2500` / `200` | 分块粒度 |
| `ASR_PROVIDER` | `local` | `local` / `openai` |
| `ASR_MODEL` | `small` | faster-whisper 模型规格 |
| `ASR_LANG` | `zh` | 识别语言 |
| `DOC_TTL_UNVERIFIED_DAYS` | `730` | L0 未验证档：从未被核对的记忆，原文留得久 |
| `DOC_TTL_VERIFIED_DAYS` | `180` | L0 已验证档：摘要已确认，原文可提前释放 |
| `AUDIO_TTL_DAYS` | `180` | 音频 TTL |
| `TRANSCRIPT_TTL_DAYS` | `365` | 转写全文 TTL |
| `SOFT_ARCHIVE_WEIGHT` | `0.10` | 软归档阈值 |
| `HARD_ARCHIVE_WEIGHT` | `0.05` | 硬归档权重阈值 |
| `HARD_ARCHIVE_IDLE_DAYS` | `180` | 硬归档空闲天数 |
| `DECAY_TASK` / `DECAY_KNOWLEDGE` / `DECAY_DECISION` | `0.95` / `0.99` / `0.995` | 各类日衰减系数 |
| `CONFLICT_SIM_GATE` | `0.35` | 相似度闸门（低于则不调 LLM） |
| `CONFLICT_AUTO_PENDING` | `0.80` | 判为 override 时进入 `pending_merge` 的置信度门槛 |
| `UPLOAD_MAX_MB` | `200` | 上传体积上限 |
| `CORS_ALLOW_ORIGINS` | 空 | 额外允许的来源（逗号分隔） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `CHUNK_MIN` / `CHUNK_TARGET` / `CHUNK_MAX` | `800` / `2500` / `6000` | 语义分块区间 |
| `TOPIC_SIM_THRESHOLD` | `0.30` | 话题漂移判定阈值 |
| `SHRINK_ENABLED` | **`false`** | 瘦身不可逆且要重算全部 offset。默认关，按 `source` 白名单开启（如 `note`、`chat`） |
| `SHRINK_MIN_AGE_DAYS` | `180` | 允许瘦身的最小材料龄 |
| `SHRINK_LIVE_REF` | `2` | 触发瘦身的活引用上限 |
| `ARCHIVE_EXPORT_YEARS` | `3` | 归档条目导出年限 |
| `DISK_WARN_PCT` | `80` | 磁盘水位，超过即收紧回收 |
| **`EMBED_*`** | **未启用** | 向量检索尚未排期（见 5.18）；启用前下列配置不读、不校验 |
| `EMBED_PROVIDER` | `local` | `local`（fastembed）/ `api`（OpenAI 兼容） |
| `EMBED_MODEL` | `BAAI/bge-m3` | 换模型必须重建向量 |
| `EMBED_DIM` | `1024` | 必须与 `memory_vectors` 声明一致，不符则拒绝启动 |
| `EMBED_QUANT` | `int8` | `int8` / `float32` |
| `VEC_TOP_K` | `50` | 语义路候选数 |
| `RRF_K` | `60` | RRF 平滑常数 |
| `CONCEPT_MARGIN` | 标定值（TF-IDF 下约 `0.05`） | 概念挂靠闸门：与第二名的差距，不是绝对余弦 |
| `CONCEPT_TOPK` | `5` | 挂靠时参与比较的候选概念数 |
