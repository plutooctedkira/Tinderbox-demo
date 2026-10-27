"""v2.22：离线写入 / 主动浮现 / Markdown 镜像。"""
import pathlib
import re

BASE = pathlib.Path(r"E:\记忆库")
OLD = BASE / "Tinderbox_记忆库完整方案_v2.21.md"
MD = BASE / "Tinderbox_记忆库完整方案_v2.22.md"
text = OLD.read_text(encoding="utf-8")
done, miss = [], []


def swap(key, old, new):
    global text
    n = text.count(old)
    if n != 1:
        miss.append(f"{key}({n})")
        return
    text = text.replace(old, new)
    done.append(key)


swap("版本", "版本：v2.21（合并稿）", "版本：v2.22（合并稿）")
for a, b in (("'schema_version','2.21.0'", "'schema_version','2.22.0'"),
             ('schema_version: str = "2.21.0"', 'schema_version: str = "2.22.0"'),
             ('to="2.21.0"', 'to="2.22.0"'), ('set_version(conn, "2.21.0")', 'set_version(conn, "2.22.0")'),
             ('schema_version: "2.21.0"', 'schema_version: "2.22.0"')):
    if a in text:
        text = text.replace(a, b)

row = "| **v2.21** | **2026-10-26** | **九条评审修正：工期上修、向量去留、归档 FTS 缺口、审计触发器、默认值** |"
swap("更新日志", row, row + "\n| **v2.22** | **2026-10-27** | **写入与增强分离（离线优先）；新增主动浮现、Markdown 镜像** |")

# ---------- 5.4 表结构 ----------
swap("5.4 字段", "    confidence        TEXT    NOT NULL DEFAULT 'medium'",
     "    confidence        TEXT    NOT NULL DEFAULT 'medium',\n"
     "    extract_state     TEXT    NOT NULL DEFAULT 'provisional',  -- provisional / refined / failed\n"
     "    refined_at        TEXT,                            -- 精修完成时间")

# ---------- 5.21 memory_revisions + Markdown 镜像 ----------
SEC521 = '''
### 5.21 修订留痕 memory_revisions

精修会**改写已入库条目的摘要**。这种改写不产生新版本（同一条事实，只是说得更清楚），但必须留痕——否则"这条怎么变了"无从追查。

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

| 规定 | 为什么 |
|---|---|
| 精修**不改** `version_no`、不建新组 | 版本链记录的是"内容改口"，不是"措辞变好" |
| 每次替换必写一行 | 审查时可以回放这条记忆的全部历史表述 |
| 只对"干净"条目精修 | 已进版本链、有冲突或有关联的条目不碰——它们已经被别的结构引用 |

'''
swap("5.21 插入", "## 6 模块设计", SEC521 + "## 6 模块设计")

# ---------- 6.6.9 写入与增强分离 ----------
SEC669 = '''
#### 6.6.9 写入与增强必须分离

早期实现里，`ingest()` 直接调 LLM 提炼——结果是**写入路径依赖外部服务**：断网写不进去，接口慢 8～21 秒，超时还要重试。这违反了一条底线：**记忆的持久化不该把命交给别人**。

拆成两条路：

| 阶段 | 做什么 | 联网 | 耗时 | 失败影响 |
|---|---|---|---|---|
| **写入** | 落 L0 → 规则提炼 L1 → 入库（`extract_state='provisional'`） | **不需要** | 十几毫秒 | 无 |
| **精修** | LLM 把摘要改写成「结论——依据」，写 `memory_revisions` | 需要 | 每条一次调用 | 保持原样，不影响已有数据 |
| **向量** | 异步补（未实装） | 需要 | — | — |

**三条实现约束**：

1. **写入路径里不允许出现任何网络调用**——包括"探活"。探活失败就阻塞写入，是本末倒置。
2. **精修必须能拒绝劣化**。LLM 会把"项目最初的构想"改写成"第一站选大学城"，事实全丢。加一道闸：新摘要比原摘要短 40% 以上、或不含"——"结构，就拒收并保持原样。
3. **只精修"干净"条目**：已进版本链（`version_no > 1`）、有冲突、有关联关系的条目不碰——它们已被别的结构引用，改一个字段会牵连一片。

**实测**（`demo/run_offline.py`）：模拟断网 → 20 条 **15 ms** 落库、全部 `provisional`、检索照常；恢复联网后精修 8 条 → 采纳 7、**驳回 1**。

'''
swap("6.6.9", "### 6.7 retriever.py", SEC669 + "### 6.7 retriever.py")

# ---------- 7.4 主动浮现 ----------
SEC74 = '''
### 7.4 对话开头的主动浮现

新对话开始时，系统要**主动**给几条记忆，而不是等人问。这是"记忆库"与"搜索框"的分界线。

**打分（纯本地、确定、可解释）**：

```text
score = 0.50 × weight + 0.30 × 新鲜度
      + 0.25  若 pin 或 anchor
      + 0.15  若该链改过 ≥2 版且现行版已 >30 天（可能已过时，该复查）
      + 0.30  若该条目有未裁决冲突
```

**必须去重，且按话题去重**：同一话题只出一条；与已选条目字面重合（Jaccard > 0.55）的也跳过。

> 第一版按"版本组"去重，结果浮现出三条同义句（一个话题的三个段落各自成了组）。**浮现错一条，用户就不再信这个功能**——宁可少给。

**每条都要带"为什么是它"**：`权重 1.00；新鲜度 0.85；改过 4 版且已 60 天，可能该复查`。人看不懂为什么浮现，就不会去看它。

**返回结构**：

```python
{"memories": [...], "pending_conflicts": 2, "provisional": 16, "total": 34}
```

`pending_conflicts` 与 `provisional` 单独返回：前者提醒"有 2 件事等你裁决"，后者提醒"还有 16 条没精修"——**都是状态，不该混进记忆列表**。

'''
swap("7.4", "## 8 衰减、归档与 TTL 管道", SEC74 + "## 8 衰减、归档与 TTL 管道")

# ---------- 5.22 Markdown 镜像 ----------
SEC522 = '''
### 5.22 Markdown 镜像

**定位先写清楚：SQLite 是主库，Markdown 是镜像。** 镜像可读、可编辑，但改了要跑 `rebuild_from_markdown` 才生效。把 md 当唯一真相源是另一套架构（每次启动重建索引），当前不做。

导出格式（人读优先，同时可被机器解析）：

```markdown
## 露营咖啡车项目记录

- **decision** · 2026-10-27 · v2 现行 · refined
  - 摘要：首站从大学城改为创业园区——因为日均只有 34 杯
  - 前因：项目最初计划把面包车改成咖啡车
  - 原文：d-3f2a [181, +120)
```

| 项 | 规定 |
|---|---|
| 分组 | 按材料（`memory_documents`）分节，条目按原文位置排序 |
| 每条的元信息 | 类别 · 日期 · 版本号与状态 · 精修状态 |
| 可编辑范围 | 摘要、前因；其余字段重建时被结构覆盖 |
| 重建代价 | **原文指向会丢**——镜像里只有 `doc_id + offset`，重建后条目不再指向 L0 |

**为什么值得做**：黑盒感是这类工具的头号劝退原因。"我存的东西到底长什么样、能不能直接改"——能回答这个问题，信任才建立得起来。

'''
swap("5.22", "## 6 模块设计", SEC522 + "\n## 6 模块设计")

# ---------- 16.1 用例 ----------
NEW_T = ("| T31 | 集成 | **断网可写入** | 模拟 LLM 不可用，灌 1 份材料 | 全部条目 `provisional`；检索可用；写入 < 100 ms |\n"
         "| T32 | 集成 | **精修不劣化** | 对 8 条跑精修 | 采纳的含「——」；被驳回的原样保留；`memory_revisions` 有记录 |\n"
         "| T33 | 集成 | **浮现不重复** | 同话题 3 条，取 top3 | 同话题只出现 1 条；每条带 `why` |\n"
         "| T34 | 集成 | **Markdown 往返** | 导出 → 人工改一行 → 重建 | 改动能被检索到；条数一致 |\n")
i = text.index("| T30 |")
j = text.index("\n", i) + 1
text = text[:j] + NEW_T + text[j:]

# ---------- 17.5 进度 ----------
swap("17.5 状态", "| **人工裁决（看板）** | 11.3 | ✅ 跑通 |",
     "| **人工裁决（看板）** | 11.3 | ✅ 跑通 |\n"
     "| **离线写入 + 异步精修** | 6.6.9 | ✅ 跑通（断网 15 ms 落库） |\n"
     "| **对话开头主动浮现** | 7.4 | ✅ 跑通（按话题去重） |\n"
     "| **Markdown 镜像** | 5.22 | ✅ 单向导出 + 可从 md 重建 |")

MD.write_text(text, encoding="utf-8")
print("已改：", done)
print("未匹配：", miss)
