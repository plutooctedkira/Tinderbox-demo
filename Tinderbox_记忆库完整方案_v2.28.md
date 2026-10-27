# Tinderbox 记忆库完整方案

**分级记忆 · 版本链 · 冷归档 · 冲突治理**

版本：v2.28（合并稿）
编制日期：2026-10-25
文档性质：技术方案与实施规范

---

## 1 文档说明

### 1.1 本文档的来源

本文档由两份既有材料合并、勘误并补齐而成：

| 编号 | 来源 | 性质 | 主要内容 |
|---|---|---|---|
| S1 | `Memory_Vault_Architecture.md` | 初版架构草稿 | SQLite + FTS5 + DeepSeek 的技术选型、主表与 FTS 结构、触发器、五个核心模块、HTTP API、看板、部署方式 |
| S2 | `一.docx` | 修改方案（评审意见） | 十一组“改/加”清单：Schema 版本字段、L1/L0 拆分、双 FTS、中文分词、事务化 supersede、冲突治理、音频链路、冷归档与 TTL、UI、导出、部署、测试、优先级 |

### 1.2 合并原则

1. **S2 的“改”优先于 S1 的原设计**，凡两者冲突，按 S2 执行。
2. **S2 未提及的 S1 内容予以保留**（如目录约定、看板形态、MCP 挂载方式），仅做一致性对齐。
3. **两稿均未写清但实现必需的细节予以补齐**，包括：可执行的完整 DDL、触发器 SQL、打分公式、状态机、并发与幂等策略、迁移脚本步骤、验收指标。补齐内容逐条记入附录 B，不做静默改动。
4. **两稿中的口径错误予以纠正**（例如衰减速率的算术不自洽、触发器与索引数量不一致），纠正理由与算式写在附录 B。

### 1.3 阅读指引

| 读者 | 建议路径 |
|---|---|
| 决策者 | 第 2 章（目标）、第 4 章（总体架构）、第 17 章（实施路线）、第 18 章（风险） |
| 后端实现 | 第 5 章（数据模型，可直接执行）、第 6 章（模块）、第 7～8 章（检索与管道）、第 15 章（迁移） |
| 前端实现 | 第 9 章（API）、第 11 章（看板） |
| 运维 | 第 13 章（部署）、第 14 章（安全）、附录 A（配置项） |

### 1.4 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | — | 初版架构草稿（S1） |
| v2.0-draft | — | 修改方案（S2） |
| **v2.0** | **2026-10-25** | **合并两份材料，补全 DDL／触发器／公式／迁移／验收，纠正口径冲突** |
| **v2.1** | **2026-10-25** | **L0 由条目级改为材料级（一份材料一个文件）；分块改为语义切分 + 滚动上下文 + 归并；新增存储回收与瘦身；归档条目 3 年导出裁剪。逐条对比见附录 D** |
| **v2.2** | **2026-10-25** | **向量检索由 P4 提入 P1；新增 `memory_vectors` 与 `embedding.py`；检索改为 FTS ⊕ 向量 RRF 融合；冲突召回改用向量为主。对比见附录 D.5** |
| **v2.3** | **2026-10-25** | **嵌入模型定为 `bge-m3`（1024 维）；向量体积、延迟目标、内存占用同步重算** |
| **v2.4** | **2026-10-25** | **一致性审计：修正性能预算、恢复接口签名、导出示例的旧状态值、索引计数口径** |
| **v2.5** | **2026-10-25** | **砍掉「加密导出」，非目标写死为不做加密；清理两处残留的 P4 旧引用** |
| **v2.6** | **2026-10-25** | **L0 保留期分档：已验证记忆 180 天、未验证 730 天——按「是否被核对过」而不是按日历删** |
| **v2.7** | **2026-10-25** | **「已核对」与「置顶/锚定」彻底分离：置顶不再触发验证，验证只能显式打标** |
| **v2.8** | **2026-10-25** | **全案更名为 Tinderbox：文档标题、代码标识、systemd 服务、路径、MCP 名称一并更新** |
| **v2.9** | **2026-10-25** | **修正命名释义：Tinderbox 出自安徒生《打火匣》，是「擦一下，东西就被叼回来」，不是「存着火种」** |
| **v2.10** | **2026-10-25** | **L1 从「只留结论」改为「结论 + 依据」：摘要必须说清凭什么这么定，而不是截断原文** |
| **v2.11** | **2026-10-25** | **新增 `context`（前因）：链首必须交代「为什么会有这件事」，后续版本只交代相对差异** |
| **v2.12** | **2026-10-26** | **新增概念层（星网）：多对多 + 层级；挂靠闸门用 margin 而非绝对余弦，附实测数据** |
| **v2.13** | **2026-10-26** | **新增记忆关系表：互补只连一条线，不作废、不建版本；三种关系的闸门不对称** |
| **v2.14** | **2026-10-26** | **UI 章补入「演变」时间线与「星网」折叠列；检索不再让用户选模式** |
| **v2.15** | **2026-10-26** | **配对优先于判定：先分言语行为（改/定/列/记），再比相似度** |
| **v2.16** | **2026-10-26** | **范围收窄：核心压到 21 人日；音频、Obsidian 导出、数据迁移植入非必要功能** |
| **v2.17** | **2026-10-26** | **写入 demo 实测：LLM 提炼的量化收益、并集判定、LLM 调用可重放** |
| **v2.18** | **2026-10-26** | **补人工裁决的交互约定；新增实现进度表，标出三块尚未落地的核心能力** |
| **v2.19** | **2026-10-26** | **补简繁归一（真实缺口）与分块器的两条实现约束，均附实测** |
| **v2.20** | **2026-10-26** | **规则提炼改为精确优先：绝对阈值 + 文档预算 + 低置信兜底，附实测分布** |
| **v2.21** | **2026-10-26** | **九条评审修正：工期上修、向量去留、归档 FTS 缺口、审计触发器、默认值** |
| **v2.22** | **2026-10-27** | **写入与增强分离（离线优先）；新增主动浮现、Markdown 镜像** |
| **v2.23** | **2026-10-27** | **TTL 回收与维护 CLI 落地；新增 lightweight 迁移（缺列自动补）** |
| **v2.24** | **2026-10-27** | **评估集与指标落地；并写明「这些数不能当验收线」的三条理由** |
| **v2.25** | **2026-10-27** | **`user_id` 去魅：单用户常量、不参与过滤、去掉两处无效索引** |
| **v2.26** | **2026-10-27** | **常量改名 `local` → `owner`（所有者身份，与部署位置无关）；补部署形态说明** |
| **v2.27** | **2026-10-27** | **补「本地/云端双兼容」的同步设计（13.8）；新增尚未实现清单（17.6）** |
| **v2.28** | **2026-10-27** | **同步收敛为 AB 两态、C 明确不做；主动浮现接入看板** |

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

### 2.4 非目标

- **不做多用户**：`user_id` 在单用户模式下**恒为 `'owner'`**——它表示**所有者身份，与部署位置无关**：本机跑、还是放到云服务器跑，都是同一个 `owner`。它既不参与任何查询过滤，也不是隔离边界。多用户是另一套设计（鉴权、配额、跨用户索引），不在当前范围；真要做时它是新增，不是开关。
- **不做分布式**：单机 SQLite，不引入消息队列与分布式锁。
- **不做通用 RAG 平台**：不追求任意文档问答，只服务“记忆条目”这一种形态。
- **不做实时 ASR**：录音以“上传后转写”的批处理方式进入，不做流式通话转写。
- **不做加密存储，也不做加密导出**：磁盘加密交给操作系统（BitLocker / VeraCrypt），导出需要加密时用 7z 之类的通用工具。产品内不做密钥管理——半吊子的加密只会给人虚假的安全感。

### 2.5 设计原则

1. **L1 常驻、L0 冷存**：主库只放可检索的摘要与索引，原始字节一律落盘。
2. **追加为主、改写为辅**：新事实新增一条，旧事实置 `superseded`，不覆盖历史。
3. **状态即语义**：`status` 表达生命周期，任何检索都必须显式声明模式。
4. **触发器保底、业务层保义**：触发器保证“任何写入路径都留痕”，业务层保证“动作可读”。
5. **一切阈值可配置**：衰减、归档、TTL、打分权重全部进配置，不写死。
6. **可回滚**：每次结构性变更都有备份与恢复命令。

---

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

### 3.4 状态机

**条目状态 `status`**

| 状态 | 含义 | 可进入自 | 可转出至 |
|---|---|---|---|
| `active` | 当前有效 | 新建、`restore` | `completed`、`pending_merge`、`archived`、`superseded` |
| `completed` | 任务已完成，仍有效 | `active` | `archived`、`superseded` |
| `pending_merge` | 与既有记忆冲突，待裁决 | `active`+冲突判定 | `active`（裁决保留）、`superseded`（裁决覆盖） |
| `archived` | 软归档，权重过低 | `active`、`completed` | `active`（`restore`）、`superseded` |
| `superseded` | 被新版本取代 | `active`、`completed`、`archived`、`pending_merge` | 不可回退（只能查看） |
| `purged` | 占位状态，仅用于 L0 已清除但条目保留 | — | — |

**原文状态 `l0_state`（条目侧快照）**

| 状态 | 含义 |
|---|---|
| `none` | 无原文留档（如用户直接手输的短句） |
| `live` | 所属材料仍在，可按 `offset/length` 取回区间 |
| `purged` | 所属材料已按回收策略删除，仅留引用与长度 |

该列由所属 `memory_documents.state` 批量同步，不单独维护。

状态转移一律通过 `storage`/`archive_manager` 的具名函数，禁止在别处直接 `UPDATE ... SET status=`。

---

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

### 4.3 写入数据流

```
输入（对话 / 录音 / 导入 / API）
  │
  ├─ 【第一步：材料整体落盘】archive_manager.put_document(text)
  │    ├─ zstd 压缩 → archive/l0/<hash>.zst（一份材料一个文件，不分块）
  │    └─ 写 memory_documents(doc_id, blob_hash, char_count, expires_at)
  │
  ├─ 【第二步：语义分块】ingest.split_semantic(text)
  │    └─ 返回 [(start, end)]，块长落在 [800, 6000]，按话题/结构优先切
  │
  ├─ 【第三步：逐块提炼】带滚动上下文
  │    ├─ 第 i 块的提示词里附前 i-1 块已提炼的结论（只读，禁止重复提炼）
  │    └─ 每块输出 [{category, l1_summary, topic, continues_previous, …}]
  │
  ├─ 【第四步：文档级归并】ingest.reduce(items)
  │    ├─ 按 topic 聚类 → 同组多条交 LLM 合并（互补/演化/重复）
  │    └─ 每组产出一个 memory_group + 1~n 条 L1（含 predecessor 链）
  │
  ├─ conflict_guard.check(candidate)          ← 与库内既有记忆比对
  │    ├─ 无关/补充 → status=active
  │    └─ 覆盖/重复 → status=pending_merge + memory_conflicts 一行
  │
  ├─ storage.insert_memory()                 ← 单事务
  │    ├─ 每条写 doc_id + l0_offset + l0_length + chunk_index
  │    └─ 触发器 → FTS + 审计
  │
  └─ exporter.enqueue(entry_id)              ← 异步
       └─ 60 s 内批量生成 .md → git add/commit/push（失败重试 3 次）
```

关键点：**L0 先于分块落盘**。分块只是“读原文的一个窗口”，原文本身始终只有一份。

### 4.4 检索数据流

```
query
  ├─ textproc.tokenize_query → tokens
  ├─ 两路并行召回（各取 50 条）
  │    ├─ 词法路：构造 MATCH 表达式 → memory_fts_active / _history
  │    └─ 语义路：embedding(query) → memory_vectors KNN（仅活跃条目有向量）
  ├─ RRF 融合（7.2）：按排名而非分数合并，避免 BM25 与 cosine 量纲不可比
  ├─ 过滤（status / source / media）→ 分组去重 → 排序
  ├─ 取 top_k 返回
  └─ 副作用：access_count+1、last_accessed_at=now、weight 回升、写 RECALL_HIT
```

**降级**：向量索引不可用（模型未加载、`sqlite-vec` 缺失、维度不符）时，整条链路自动退化为纯 FTS，响应里带 `degraded: "vector_unavailable"`，不报错。

**写回权重**：命中即“被使用”，`weight = min(1.0, weight + 0.05)`（`pin/anchor` 不变），使真正的常用记忆抗衰减。

### 4.5 与初版架构的关键差异

| 维度 | v1（草稿） | v2（本方案） |
|---|---|---|
| 记忆粒度 | 单层 `content` | L1 摘要 + L0 原文两级 |
| 版本 | `supersede` 二元替代 | 版本组 + 版本链 + 前驱指针 |
| FTS | 单表 `memory_fts`（全部状态） | 双表 active/history + 归档表 |
| 中文 | `unicode61` 直索引（实际不可用） | jieba 预分词写入 |
| 生命周期 | 权重衰减 → 归档 | 衰减 → 软归档 → 硬归档 → L0/媒体 TTL |
| 冲突 | 只列“冲突列表”（未定义判定） | `conflict_guard` 三级判定 + 人工裁决 |
| 音视频 | 无 | `memory_media` + ASR 适配 + 转写管道 |
| 删除 | `SET l0_raw_content=NULL` | 压缩冷归档 + TTL + 回收站 |

---

## 5 数据模型

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

**为什么单独设 `memory_blobs`**：S2 要求“同哈希 L0/音频只存一份，多条目共享”。若把物理路径直接写在 `memory_documents` 与 `memory_media` 上，同内容会产生多行、多文件，删除时无法判断是否还有引用。把「物理文件」抽为 `memory_blobs`（`hash` 为主键、`ref_count` 计数），上层两张表只做**逻辑索引**，去重与回收才有唯一真相源。

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

**连接约定**：

- 一连接一线程，`check_same_thread=False` 仅在**连接不跨线程复用**时使用；
- 写事务一律 `BEGIN IMMEDIATE`（避免读锁升级死锁），并在 `contextlib.contextmanager` 中管理；
- 长事务禁止包含 LLM 调用（网络等待会持有写锁），LLM 结果先在事务外算好再入库。

### 5.3 元数据表

```sql
CREATE TABLE memory_schema_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

INSERT OR IGNORE INTO memory_schema_meta(key, value) VALUES ('schema_version','2.24.0');
```

用途：迁移脚本据此判断当前版本，禁止“猜测式升级”。

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

**字段说明与设计决策**

| 字段 | 决策与理由 |
|---|---|
| `row_id` | 新增整型主键。S1/S2 均以 `entry_id` 为 TEXT 主键，但 FTS5 只能按 `rowid` 高效删除；TEXT 主键表的 rowid 在 `VACUUM` 时可能变化，会导致 FTS 与主表错位。故增设 `AUTOINCREMENT` 整型主键，`entry_id` 降为 `UNIQUE` 业务键 |
| `content → l1_summary` | 语义是**“结论 + 依据”**，不是“截断的原文前 120 字”。`NOT NULL` + 长度上限 4000，防止 LLM 输出失控 |
| `tokenized_content` | jieba 分词后的空格分隔文本，FTS 只索引它，不再索引原文，避免“整句一个 token” |
| `l1_hash` | 内容去重：同用户同 hash 的 active 条目拒绝重复插入（幂等写入的基础） |
| `l0_offset/l0_length` | 多个 L1 可能来自同一份 L0（如长文分块），记录片段位置即可共享一份 blob |
| `importance` | 参与衰减调制（第 8 章），高重要性衰减更慢 |
| `context` | **前因**：这个话题为什么会存在（缘起 / 计划 / 约束）。**只给链首填**——`version_no = 1` 的那条；后续版本靠 `predecessor_id` 回溯，不必重复背景 |
| `verified_at` | 摘要是否被人核对过。它**不改变记忆本身**，只改变原文能留多久（8.3）：确认过 → 180 天，从未确认 → 730 天。**只能显式打标**，不从 `pin`/`anchor` 推导——置顶是组织方式，核对是质量判断 |
| `valid_from/valid_to` | 表达“事实有效期”，与 `created_at` 解耦：记忆写入时间 ≠ 事实生效时间 |
| `weight/access_count` | 权重用于衰减与排序；`access_count` 供统计与“热度回升” |

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

`is_open = 0` 表示该话题已收敛（如“已完成的部署任务”），后续相似记忆不再并入本组，而是新建组——避免“万能组”越滚越大。

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

**引用计数规则**

- 新增引用：`ref_count = ref_count + 1`（同事务）；若行已存在且 `state='purged'`，则重建文件。
- 解除引用：`ref_count = ref_count - 1`；归零后置 `state='orphan'`，**不立即删文件**（给 7 天宽限）。
- 对账：`maintenance` 每晚比对 `memory_blobs` 与磁盘目录，双向修复（DB 有文件无 → 标记 missing 告警；文件有 DB 无 → 移入 `archive/_orphan/`）。

### 5.7 材料表 memory_documents

一份材料——一次导入的文档、一段对话、一次录音的转写全文——对应**一个** L0 文件，不分块存。本表记录材料的物理位置、规模与冻结状态。

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

**口径**

| 项 | 规定 |
|---|---|
| 一份材料一个文件 | 5 万字文档 = 1 个 zstd 文件 + N 条 L1，每条 L1 用 `l0_offset/l0_length` 指向区间 |
| 分块不分存储 | 分块只影响“一次喂给模型多少”，不影响物理布局 |
| 不能局部删 | zstd 整体压缩，无法“抠掉一段”；只能整份保留，或整份重写（6.10.3 瘦身） |
| `live_ref_count` | 每晚由对账任务一条 `GROUP BY` 刷新，供回收判断与看板显示，**不做实时维护** |
| `state='shrunk'` | 已瘦身：文件只保留仍被引用的区间；`char_count` 保留原值供审计 |
| `entry_count` | 该文档产出过多少条 L1（含已归档），用于统计“提炼密度” |

> **与 S2 的差异（记入附录 D）**：S2 提出 `memory_l0_archive`，主键 `entry_id`、`blob_hash` 带 `UNIQUE`。这与“多条 L1 共享一份原文”直接冲突——第 2 条 L1 写归档记录时就会撞唯一约束。本方案把“原文归档”与“材料登记”合并为 `memory_documents`（主键 `doc_id`），**删除 `memory_l0_archive`**，同一事实不再存两处；条目级“原文还在不在”由 `memory_entries.l0_state` 缓存，随文档状态批量同步。

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

`blob_hash` 上**不加** `UNIQUE`：同一次录音可能被重复上传，去重发生在 blob 层（`memory_blobs.hash` 主键），媒体行仍按上传次数各留一条，便于追溯。

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

S2 只在条目上提了 `pending_merge` 状态，未定义冲突的存放位置。仅靠状态无法表达“和谁冲突、判定依据、建议动作”，看板的冲突页也无法排序展示。因此建独立表，`status='pending_merge'` 与之**同时写**，二者由同一事务保证一致。

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

结构与 `memory_entries` 一致（不含 FTS），另加两列。为免 DDL 与主表手工同步出错，采用“克隆空表”写法：

```sql
-- 归档表的列、约束、默认值与 memory_entries 完全一致，只多一列 archived_at。
-- 不要用 CREATE TABLE AS SELECT：它不复制主键、CHECK、默认值，主表加列时要靠人记得重建。
-- 迁移脚本的做法：拷贝 5.4 的 DDL → 改表名 → 追加 archived_at 一列。
CREATE TABLE memory_entries_archive ( ...同 memory_entries... ,
    archived_at TEXT );
ALTER TABLE memory_entries_archive ADD COLUMN archive_reason TEXT;  -- weight_low / ttl / manual
CREATE INDEX idx_archive_archived_at ON memory_entries_archive(archived_at);
```

> **注意**：归档表用**完整 DDL**（同 `memory_entries`，多一列 `archived_at`），不用 `CREATE TABLE AS SELECT`。后者不复制主键、CHECK、默认值，且主表每加一列都要人工重建一次——漏一次，归档写入就整批失败。`db.py` 启动自检仍比对两表列集合，不一致直接拒绝启动。

**归档必须同步 FTS**：硬归档是「INSERT 归档表 + DELETE 主表」，主表的 `trg_fts_ad` 只会清 active/history 索引，**没有任何触发器往 `memory_fts_archive` 写**——`include_archive=True` 会查不到东西。补两个触发器：

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

**为什么是“外挂表 + rowid 对齐”而不是 `content=` 外部内容表**

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| `content=memory_entries`（外部内容） | 不重复存储正文，省空间 | 触发器必须回填旧值才能正确删除；无法按 `status` 分区（一个 FTS 表只能索引整张表的行） | 不采用（与“双 FTS”目标冲突） |
| 独立 FTS 表 + `rowid = memory_entries.row_id` | 可按状态分区；删除 O(1)；逻辑简单 | 正文重复存储，索引体积约 1.2～1.5 倍 | **采用** |
| `contentless_delete=1`（SQLite ≥ 3.43） | 省空间且可删除 | 版本依赖强，Python 内置 SQLite 版本不可控 | 后续可选优化（未排期） |

**分词策略**

- 索引侧：`jieba.cut_for_search(text)`（搜索模式，长词切出短词，提升召回），过滤停用词与纯符号，用单个空格连接写入 `tokenized_content`。
- 查询侧：`jieba.cut_for_search(query)`，同样过滤，构造 `"tok1" AND "tok2"`。
- 降级：`AND` 命中数 < 3 时自动改 `"tok1" OR "tok2"`，并按命中比例加权，避免“多词必不中”。
- 词典：`var/userdict.txt` 随项目分发，锁定 `jieba` 版本（`requirements.txt` 精确版本号）。**词典或版本变更后必须全量重建 FTS**，否则新旧分词口径混用。

### 5.13 索引清单

| # | 索引名 | 表 | 列 | 用途 |
|---|---|---|---|---|
| 1 | `idx_entries_status` | memory_entries | (status) | 看板「全部/归档」列表（原 `(user_id, status)` 的 user_id 是常量，索引无效） |
| 2 | `idx_entries_group_version` | memory_entries | (memory_group_id, version_no) | 版本链展开 |
| 3 | `idx_entries_status_weight` | memory_entries | (status, weight) | 衰减扫描、浮现排序 |
| 4 | `idx_entries_l0_state` | memory_entries | (l0_state) | TTL 扫描定位待归档 |
| 5 | `idx_entries_media` | memory_entries | (media_id) | 媒体反查条目 |
| 6 | `idx_entries_updated` | memory_entries | (updated_at DESC) | 增量导出、对账 |
| 7 | `idx_entries_l1_hash` | memory_entries | (l1_hash) | 幂等去重（同上，去掉常量前导列） |
| 8 | `idx_media_entry` | memory_media | (entry_id) | 媒体反查 |
| 9 | `idx_media_hash` | memory_media | (blob_hash) | 去重校验 |
| 10 | `idx_media_expires` | memory_media | (expires_at) | TTL 扫描 |
| 11 | `idx_docs_expires` | memory_documents | (expires_at) | 材料 TTL 扫描 |
| 12 | `idx_docs_live_ref` | memory_documents | (state, live_ref_count) | 回收扫描 |
| 13 | `idx_entries_doc` | memory_entries | (doc_id) | 按材料反查条目 |
| 14 | `idx_blobs_state` | memory_blobs | (state, expires_at) | 孤儿回收 |
| 15 | `idx_conflicts_state` | memory_conflicts | (state, created_at) | 冲突列表 |
| 16 | `idx_logs_entry_ts` | memory_logs | (entry_id, ts) | 单条追溯 |
| 17 | `idx_logs_action_ts` | memory_logs | (action, ts) | 审计导出、统计 |

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

> 磁盘空间权衡：以上 18 个索引（含归档表 1 个）约占用主表体积的 25%～35%。若写入压力大，可只保留 1～8、11、13，其余按查询计划按需增补（用 `EXPLAIN QUERY PLAN` 验证后再加）。

### 5.14 触发器：FTS 同步（3 个）

触发器只负责“把变化同步到正确的 FTS 表”，不承担业务语义。三个触发器通过 `rowid` 对齐，保证删除为 O(1)。

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

> `AFTER UPDATE OF <列>` 保证只在这两列出现在 `SET` 子句中时触发，这是“访问不触发重建”的第一道闸；`WHEN` 条件再排除“值未变”的空转，是第二道闸。

### 5.15 触发器：审计（3 个）

审计触发器只记录**语义敏感字段**的变化，不记录 `weight`、`access_count`、`last_accessed_at`。原因：衰减每晚会对全表做权重更新，若逐行记日志，10 万条 × 365 天 ≈ 3650 万行，纯属噪声。

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

**“避免双记”的明确分工**

| 记录者 | `action` 取值 | 目的 | 看板是否展示 |
|---|---|---|---|
| 触发器 | `INSERT`、`FIELD_DIFF`、`PURGE` | 字段级完整性：任何写入路径（含手工 SQL、未来脚本）都留痕 | 否（仅审计导出） |
| 业务层 | `SUPERSEDE`、`ARCHIVE`、`RESTORE`、`RECALL_HIT`、`DECAY`、`L0_*`、`TRANSCRIBE`、`CONFLICT_*`、`UPLOAD_AUDIO` | 语义可读：谁、为什么、做了什么 | 是 |

两者不重复，因为一条记录的“发生了什么”（语义）与“哪几列变了”（字段）是不同粒度的信息。

> **关于 `PURGE`**：`trg_audit_ad` 无法区分“硬归档搬移”与“人工物理删除”——在数据库层面两者都是 `DELETE`，因此触发器统一记 `PURGE`（字段级）。语义层由业务代码补记 `HARD_ARCHIVE`（硬归档）或 `PURGE`（人工删除），审计时以“同一时刻是否存在语义记录”来区分。

### 5.16 触发器与索引数量核对

| 对象 | 数量 | 明细 |
|---|---|---|
| 表 | 9 | 上述 9 张普通表。**`memory_vectors` 不在此列**——它是预留设计，见 5.18 的说明 |
| FTS5 虚拟表 | 3 | memory_fts_active、memory_fts_history、memory_fts_archive |
| 触发器 | **6** | 3 个 FTS 同步 + 3 个审计 |
| 索引 | 18 | 主库 17 个（5.13）+ 归档表 1 个 `idx_archive_archived_at`（5.11）。向量表未启用，不计入 |

> S1 中“6 个触发器”与“9 个触发器”两处自相矛盾，本方案统一为 **6 个**：FTS 同步从 S1 的“3 个单表触发器”演进为“3 个双表路由器”，审计维持 3 个。

### 5.17 完整性自检

`db.py` 启动时执行（任一失败即拒绝启动并打印修复指引）：

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

FTS 内部一致性检查（每周 `maintenance` 执行）：

```sql
INSERT INTO memory_fts_active(memory_fts_active)  VALUES('integrity-check');
INSERT INTO memory_fts_history(memory_fts_history) VALUES('integrity-check');
INSERT INTO memory_fts_active(memory_fts_active)  VALUES('optimize');
INSERT INTO memory_fts_history(memory_fts_history) VALUES('optimize');
```

### 5.18 向量索引 memory_vectors

> **状态：预留设计，当前不建表。**
> 本节描述的是“如果做向量”长什么样。在 17.4 把向量排进路线图之前：**不创建 `memory_vectors`、不设 `EMBED_*` 配置、
> 表与索引清单（5.12）也不计它**。这样实现者不会面临“到底建不建”的困惑。
> 决策依据：30 条实测中 LSA 未证明收益（附录 D.18）；等换到真模型、且样本上到几百条再重评。

向量只为**活跃条目**服务：写入时生成，归档时删除。它不是档案，是召回加速器——因此不随条目一起变老，也不占历史存储。

```sql
-- 需要 sqlite-vec 扩展（v0.1.6+）
-- 预留设计：向量检索未排期，当前**不建这张表**；启用时同步打开 附录 A 的 EMBED_*
CREATE VIRTUAL TABLE memory_vectors USING vec0(
    row_id    INTEGER PRIMARY KEY,          -- 与 memory_entries.row_id 对齐
    embedding int8[1024]                    -- bge-m3，int8 量化，体积为 float32 的 1/4
);
```

| 项 | 规定 |
|---|---|
| 维度 | 固定 1024（bge-m3），配置项 `EMBED_DIM`。改维度 = 全量重建，故写死在 schema 里并由自检拦截 |
| 量化 | `int8`。1024 维下每条 1 KB；10 万条约 102 MB，float32 则需 410 MB |
| 查询缓存 | 最近 1024 条查询向量的 LRU，命中即 0 ms——重复问同一件事不必重复编码 |
| 生命周期 | `status IN ('active','completed','pending_merge')` 时存在；转 `archived/superseded` 时由业务层删除该行 |
| 一致性 | 不做触发器同步（vec0 不支持常规触发器语义），由 `storage` 在同一事务内维护；每日对账比对行数 |
| 重建 | `python -m src.maintenance reindex --vectors`，支持断点续跑，按 `row_id` 区间分批 |
| 不可用 | 扩展缺失或模型未加载时，`memory_vectors` 视为空表，检索自动降级为纯 FTS |

**为什么量化到 int8**：检索要的是“排序大致正确”，不是“余弦值精确到小数点后六位”。int8 量化的召回损失通常在 1% 以内，换来 4 倍空间与更快的距离计算。

**为什么只给活跃条目**：归档条目已从“现在”退场，历史检索靠 `memory_fts_history` 足够；给全部历史存向量会让主库从 225 MB 涨到 635 MB，直接击穿 G3。


### 5.19 概念层 memory_concepts

版本组只解决“同一件事的第几版”，解决不了“哪几件事属于同一个项目”。`豆子从哪来` 和 `选址` 之间没有共同父节点，于是“给我讲讲咖啡车项目”做不到——这是星网要补的一层。

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

| 设计点 | 规定 | 为什么 |
|---|---|---|
| 多对多 | 一条记忆可同时挂 `豆子从哪来`、`豆子供货商决策`、`咖啡车生意` | 现实里一个事实本就属于多个上下文 |
| 层级 | `parent_id` 自引用；查某概念默认**带子孙** | “问项目”要能聚合到所有子话题 |
| `kind` | `manual` 人建 / `derived` 标题推导 / `proposed` 机器提议待命名 | 三种来源的可信度不同，界面上要能区分 |
| `is_seed` | 人指定的锚点成员；有种子时质心**只按种子算** | 解决“质心漂移”：新成员不改变概念的语义 |

**明确不做**：概念里不存向量。质心按需从成员实时算（6.15），避免“存了一份、成员变了没更新”的不一致。


### 5.20 记忆关系表 memory_relations

“互补”不改变任何一方——两条记忆都还成立，只是相关。所以它不占 `status`、不建版本、不进冲突队列，单独一张表。

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

| 项 | 规定 |
|---|---|
| 方向 | `from_entry` 是后写入的那条，`to_entry` 是被补充的那条；查询时**两个方向都要看** |
| 不参与排序 | 关系只影响“看这条时能看到那条”，**不改变 `score`** |
| 级联 | 任一端被删除，关系随之删除（`ON DELETE CASCADE`） |
| 与版本链的区别 | 版本链是**替代**（A 不再有效）；关系是**并列**（A 仍然有效） |


### 5.21 修订留痕 memory_revisions

精修会**改写已入库条目的摘要**。这种改写不产生新版本（同一条事实，只是说得更清楚），但必须留痕——否则“这条怎么变了”无从追查。

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
| 精修**不改** `version_no`、不建新组 | 版本链记录的是“内容改口”，不是“措辞变好” |
| 每次替换必写一行 | 审查时可以回放这条记忆的全部历史表述 |
| 只对“干净”条目精修 | 已进版本链、有冲突或有关联的条目不碰——它们已经被别的结构引用 |


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

**为什么值得做**：黑盒感是这类工具的头号劝退原因。“我存的东西到底长什么样、能不能直接改”——能回答这个问题，信任才建立得起来。


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

### 6.2 config.py

所有阈值集中于一处，禁止散落魔法数字。配置优先级：环境变量 > `.env` > 代码默认值。

```python
from dataclasses import dataclass, field
import os

@dataclass(frozen=True)
class Settings:
    # --- 存储 ---
    db_path: str = os.getenv("DB_PATH", "memory.db")
    archive_root: str = os.getenv("ARCHIVE_ROOT", "archive")
    vault_path: str = os.getenv("VAULT_PATH", "vault")
    schema_version: str = "2.24.0"

    # --- LLM ---
    llm_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    llm_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    llm_timeout: float = 60.0
    llm_max_retry: int = 3
    l1_max_chars: int = 400
    chunk_min: int = 800
    chunk_target: int = 2500
    chunk_max: int = 6000
    topic_sim_threshold: float = 0.30

    # --- 检索 ---
    fts_candidate_limit: int = 50
    vec_top_k: int = 50
    default_top_k: int = 10
    rrf_k: int = 60
    w_rel: float = 0.60
    w_rec: float = 0.25
    w_weight: float = 0.15
    access_weight_boost: float = 0.05

    # --- 衰减（日乘数） ---
    decay_task: float = 0.95
    decay_decision: float = 0.995
    decay_knowledge: float = 0.99
    decay_preference: float = 0.99
    decay_fiction: float = 0.995
    soft_archive_threshold: float = 0.10
    hard_archive_weight: float = 0.05
    hard_archive_idle_days: int = 180

    # --- TTL 与回收 ---
    doc_ttl_days: int = 365
    audio_ttl_days: int = 180
    transcript_ttl_days: int = 365
    orphan_grace_days: int = 7
    trash_grace_days: int = 7
    shrink_enabled: bool = False   # 瘦身不可逆、无回收站，默认关
    shrink_min_age_days: int = 180
    shrink_live_ref: int = 2
    archive_export_years: int = 3
    disk_warn_pct: int = 80

    # --- 冲突 ---
    conflict_candidates: int = 5
    conflict_similarity_gate: float = 0.35
    conflict_auto_pending: float = 0.80

    # --- 向量 ---
    embed_provider: str = os.getenv("EMBED_PROVIDER", "local")   # local | api
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
    embed_dim: int = 1024                # 必须与 memory_vectors 声明一致
    embed_quant: str = "int8"            # int8 | float32

    # --- 安全 ---
    api_token: str = os.getenv("API_TOKEN", "")
    bind_host: str = os.getenv("BIND_HOST", "127.0.0.1")
    bind_port: int = int(os.getenv("BIND_PORT", "8765"))
    upload_max_mb: int = 200
    sign_secret: str = os.getenv("SIGN_SECRET", "")
```

### 6.3 textproc.py

分词的唯一出口。所有模块共用，保证“写进去的”与“查出来的”是同一套口径。

```python
import hashlib, re, unicodedata
import jieba

_STOP = set("""
    的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着
    没有 看 好 自己 这 那
""".split())
_CTRL = re.compile(r"[\u0000-\u001f\u007f]+")
_WS   = re.compile(r"\s+")

def normalize(text: str) -> str:
    """NFKC 归一 + 去控制字符 + 折叠空白。中英文混排不会因全角/半角差异漏检。"""
    text = unicodedata.normalize("NFKC", text or "")
    text = _CTRL.sub(" ", text)
    return _WS.sub(" ", text).strip()

def to_simplified(text: str) -> str:
    """繁 → 简。FTS5 的 unicode61 **不做简繁归一**，不转就只有一边能命中。"""
    return text.translate(T2S_TABLE)

def tokenize_tokens(text: str, for_index: bool = True) -> list[str]:
    text = normalize(text)
    cut = jieba.cut_for_search(text) if for_index else jieba.cut(text)
    out = []
    for t in cut:
        t = t.strip().lower()
        if not t or t in _STOP:
            continue
        if len(t) == 1 and not t.isalnum():   # 丢弃孤立符号
            continue
        out.append(t)
    # 去重保序：同一 token 重复出现对 BM25 无益，反而放大短文本权重
    return list(dict.fromkeys(out))

def tokenize_index(text: str) -> str:
    return " ".join(tokenize_tokens(text, for_index=True))

def build_match(query: str, mode: str = "and") -> str:
    """构造 FTS5 MATCH 表达式。tokens 一律加双引号，防止用户输入 OPERATOR 造成语法错误。"""
    toks = tokenize_tokens(query, for_index=False)
    if not toks:
        return ""
    quoted = ['"' + t.replace('"', '""') + '"' for t in toks]
    op = " AND " if mode == "and" else " OR "
    return op.join(quoted)

def content_hash(text: str, n: int = 16) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:n]
```


#### 6.3.1 简繁归一

`unicode61` 会把 `長` 和 `长` 当成两个不同的字。不处理的话，同一份材料里繁体原文与简体查询永远对不上。

**实测**（鲁迅《呐喊》四篇，13,983 字，原著为繁体）：

| 查询 | 归一前 | 归一后 |
|---|---|---|
| 长衫（原文作「長衫」） | **0 条** | 2 条 |
| 闰土（原文作「閏土」） | 0 条 | 2 条 |
| 故乡 / 故鄉 | 0 / 1 条 | 2 / 2 条 |

**做法**：在 `normalize()` 之后、分词之前统一转简体，**索引与查询走同一个函数**。

```python
# 498 对高频繁简字；不追求 OpenCC 的完整表
T2S_TABLE = {ord("長"): "长", ord("鄉"): "乡", ...}

def tokenize_tokens(text: str, for_index: bool = True) -> list[str]:
    text = to_simplified(normalize(text))
    ...
```

| 项 | 实测 |
|---|---|
| 表规模 | 498 对 |
| 语料覆盖率 | 约 **15%** 的汉字出现次数（每 7 个字有 1 个被转） |
| 不覆盖 | 生僻异体、古籍罕见字 |

**为什么不用 OpenCC**：它要装依赖（当前环境装不了），而高频 500 字已能吃掉绝大多数日常文本。缺失的字会原样保留——**不会出错，只会漏检**，这是可接受的降级。

**一个实现提醒**：表是“两字一组”的字符串，必须逐行校验长度为偶数，并且**检测自配对**（`诗` 写成 `诗诗` 这种笔误）。实测写表时就踩了两次，靠断言才没静默失效。

### 6.4 db.py

```python
import sqlite3
from contextlib import contextmanager

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=30000",
    "PRAGMA wal_autocheckpoint=1000",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA mmap_size=268435456",
    "PRAGMA cache_size=-16384",
)

def get_db_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    for p in PRAGMAS:
        conn.execute(p)
    return conn

@contextmanager
def write_tx(conn):
    """写事务：BEGIN IMMEDIATE 直接拿写锁，避免读→写升级时死锁。"""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise

def init_db(db_path: str) -> None:
    conn = get_db_connection(db_path)
    conn.executescript(SCHEMA_SQL)      # 5 章全部 DDL，全部使用 IF NOT EXISTS
    conn.executescript(TRIGGER_SQL)     # 5.14 / 5.15
    check_schema(conn)                  # 5.17 自检，失败抛 SchemaError
    conn.close()
```

**迁移入口**：`init_db` 只建“缺失对象”，不改“已有对象”。任何列类型/约束变更都必须走 `src/migrations/v2_0_0.py`，并在 `memory_schema_meta` 中推进版本号。启动时若 `memory_schema_meta.schema_version` 与代码期望不符，直接退出并提示执行 `python -m src.maintenance migrate`。

### 6.5 storage.py

#### 6.5.1 写入：Append-Only

“追加为主”意味着 `insert_memory` **永不更新已有条目的语义字段**。它只做三件事：必要时建组、插入新行、把 L0 引用登记好。

```python
def insert_memory(conn, *, user_id, l1_summary, category, source="conversation",
                  session_id=None, confidence="medium", importance=0.5,
                  doc_id=None, l0_offset=None, l0_length=None, chunk_index=None,
                  media_id=None, valid_from=None, valid_to=None,
                  group_id=None, dedupe=True) -> dict:
    l1_summary = normalize(l1_summary)
    if not l1_summary:
        raise ValueError("EMPTY_L1")
    if len(l1_summary) > settings.l1_max_chars * 2:
        raise ValueError("L1_TOO_LONG")

    tokenized = tokenize_index(l1_summary)
    l1_hash   = content_hash(l1_summary)

    with write_tx(conn) as c:
        if dedupe:
            row = c.execute(
                "SELECT * FROM memory_entries WHERE user_id=? AND l1_hash=? "
                "AND status IN ('active','completed') LIMIT 1",
                (user_id, l1_hash)).fetchone()
            if row:                                  # 幂等：同一内容重复写入直接返回旧条目
                return dict(row, deduped=True)

        grp = ensure_group(c, user_id=user_id, topic=make_topic(l1_summary),
                           category=category, group_id=group_id)
        ver = append_version(c, grp)                 # 计算 version_no / predecessor_id

        entry_id = new_id("mem")
        c.execute("""
            INSERT INTO memory_entries(
                entry_id, user_id, session_id, memory_group_id, root_id, version_no,
                predecessor_id, category, l1_summary, tokenized_content, l1_hash,
                doc_id, l0_offset, l0_length, chunk_index, l0_state,
                media_id, source, confidence, importance, valid_from, valid_to)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (entry_id, user_id, session_id, grp["group_id"], grp["root_id"], ver["version_no"],
             ver["predecessor_id"], category, l1_summary, tokenized, l1_hash,
             doc_id, l0_offset, l0_length, chunk_index,
             "live" if doc_id else "none",
             media_id, source, confidence, importance, valid_from, valid_to))
        # L0 的 blob 引用与 TTL 在 put_document() 时已登记，此处不再重复计数

        exporter.enqueue(entry_id)                   # 异步，不阻塞事务
        return {"entry_id": entry_id, "group_id": grp["group_id"],
                "version_no": ver["version_no"], "deduped": False}
```

#### 6.5.2 取代：单事务 + 乐观锁

`supersede_memory` 是唯一允许“改写旧条目”的入口，必须原子完成四件事：

1. 校验旧条目存在、状态允许被取代、版本号未被并发改动（乐观锁）；
2. 旧条目 → `status='superseded'`、`superseded_by=新ID`、`valid_to=now`；
3. 新条目 → 同组 `version_no = old.version_no + 1`、`predecessor_id=旧ID`、`status='active'`；
4. 写一条 `SUPERSEDE` 语义日志（含新旧 L1 摘要）。

```python
class StaleVersion(Exception): ...

def supersede_memory(conn, *, old_entry_id, new_l1_summary, new_category=None,
                     new_confidence=None, expected_version_no=None,
                     actor="api") -> dict:
    l1 = normalize(new_l1_summary)
    tokenized, l1_hash = tokenize_index(l1), content_hash(l1)

    with write_tx(conn) as c:
        old = c.execute("SELECT * FROM memory_entries WHERE entry_id=?",
                        (old_entry_id,)).fetchone()
        if old is None:
            raise ValueError("NOT_FOUND")
        if old["status"] == "superseded":
            raise ValueError("ALREADY_SUPERSEDED")
        if expected_version_no is not None and old["version_no"] != expected_version_no:
            raise StaleVersion(f"expected {expected_version_no}, got {old['version_no']}")

        # 乐观锁：仅当版本号仍等于读到的值时更新，rowcount=0 说明有人抢先
        cur = c.execute("""UPDATE memory_entries
                              SET status='superseded', superseded_by=?,
                                  valid_to=COALESCE(valid_to, ?), updated_at=?
                            WHERE entry_id=? AND version_no=? AND status<>'superseded'""",
                        (None, now_iso(), now_iso(), old_entry_id, old["version_no"]))
        if cur.rowcount != 1:
            raise StaleVersion("concurrent supersede detected")

        new_id_ = new_id("mem")
        c.execute("""INSERT INTO memory_entries(
                        entry_id, user_id, session_id, memory_group_id, root_id, version_no,
                        predecessor_id, category, l1_summary, tokenized_content, l1_hash,
                        l0_state, source, confidence, importance, valid_from)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,'none',?,?,?,?)""",
                  (new_id_, old["user_id"], old["session_id"], old["memory_group_id"],
                   old["root_id"], old["version_no"] + 1, old_entry_id,
                   new_category or old["category"], l1, tokenized, l1_hash,
                   old["source"], new_confidence or old["confidence"],
                   old["importance"], now_iso()))
        c.execute("UPDATE memory_entries SET superseded_by=? WHERE entry_id=?", (new_id_, old_entry_id))
        c.execute("""UPDATE memory_groups
                        SET current_version_no=?, entry_count=entry_count+1, updated_at=?
                      WHERE group_id=?""",
                  (old["version_no"] + 1, now_iso(), old["memory_group_id"]))
        c.execute("""INSERT INTO memory_logs(entry_id, group_id, action, old_value, new_value, actor)
                     VALUES (?,?, 'SUPERSEDE', ?, ?, ?)""",
                  (old_entry_id, old["memory_group_id"],
                   json.dumps({"entry_id": old_entry_id, "l1": old["l1_summary"]}, ensure_ascii=False),
                   json.dumps({"entry_id": new_id_, "l1": l1}, ensure_ascii=False), actor))
        exporter.enqueue(new_id_)
        return {"entry_id": new_id_, "version_no": old["version_no"] + 1,
                "superseded": old_entry_id}
```

> 注意 `superseded_by` 在插入新行后才回填。这样设计是因为新 ID 需在插入前生成，而 `old.superseded_by` 需要指向它；两次 `UPDATE` 与插入同处一个 `IMMEDIATE` 事务，外部观察不到中间态。

#### 6.5.3 其他写入原语

| 函数 | 语义 | 关键约束 |
|---|---|---|
| `soft_delete(conn, entry_id)` | `status='archived'` + `SOFT_DELETE` 日志 | 不删 FTS，转入 history |
| `restore_entry(conn, entry_id)` | `status='active'` + `weight=0.5` 保底 | 若同组已有 active，先触发冲突裁决 |
| `set_pin(conn, entry_id, v)` | 置顶开关（组织手段） | `pin=1` 时 `weight` 不低于 0.5；**不写 `verified_at`** |
| `set_anchor(conn, entry_id, v)` | 锚定开关（豁免衰减与 TTL） | 与 `pin` 独立 |
| `mark_completed(conn, entry_id)` | 任务完成 | 仅 `category='task'` 可调用 |
| `mark_verified(conn, entry_id, by, reason)` | 显式标记摘要已被核对 | 幂等；`reason ∈ authored/adjudicated/reviewed`；影响 L0 保留档位 |
| `resolve_conflict(conn, conflict_id, resolution, actor)` | 裁决冲突 | 见 6.9 |

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

### 6.7 retriever.py

接口与实现见第 7 章。此处只列必须保持的契约：

```python
def retrieve_memories(conn, *, user_id: str, query: str, top_k: int = 10,
                      mode: str = "active",          # active | history | hybrid
                      include_archive: bool = False,
                      source: str | None = None,
                      media_only: bool = False,
                      group_dedup: bool = True,
                      touch: bool = True) -> list[dict]: ...
```

- 返回项必须含：`entry_id, l1_summary, category, status, weight, score, group_id, version_no, superseded_by, l0_state, media_id, created_at, valid_from, valid_to, matched_mode`
- `touch=True` 时更新 `access_count/last_accessed_at/weight` 并写 `RECALL_HIT`；只读场景（看板预览、MCP 探测）传 `False`

### 6.8 version_chain.py

```python
def ensure_group(conn, *, user_id, topic, category=None, group_id=None) -> dict:
    """group_id 给定时复用；否则新建。topic 只用于展示，不参与相似判定。"""

def append_version(conn, group: dict) -> dict:
    """返回 {version_no, predecessor_id}；predecessor 取组内当前 active 条目。"""

def expand_chain(conn, group_id: str) -> list[dict]:
    """按 version_no 升序返回整条链，附每条的 status / superseded_by / 时间。"""

def timeline(conn, group_id: str) -> dict:
    """给 UI 用：{group, entries[], spans[{entry_id, from, to}]}，spans 由 valid_from/to 推导。"""

def resolve_latest(conn, entry_id: str) -> dict:
    """沿 superseded_by 一路走到链尾，供看板"点击失效记忆跳最新"使用。"""
```

**并发安全**：`append_version` 必须读 `SELECT MAX(version_no)` 后立刻插入，且二者同事务（`BEGIN IMMEDIATE` 已持写锁）。`UNIQUE(memory_group_id, version_no)` 是最后一道防线——即使逻辑有误，并发也会以 `IntegrityError` 失败而非产生重复版本号。

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

### 6.10 archive_manager.py

#### 6.10.1 Blob 写入（压缩 + 去重 + 原子落盘）

```python
def put_blob(conn, data: bytes, *, kind: str, mime: str | None = None,
             ttl_days: int | None = None) -> str:
    raw_hash = hashlib.sha256(data).hexdigest()
    row = conn.execute("SELECT * FROM memory_blobs WHERE hash=?", (raw_hash,)).fetchone()
    if row and row["state"] == "live":
        conn.execute("UPDATE memory_blobs SET ref_count=ref_count+1 WHERE hash=?", (raw_hash,))
        return raw_hash                                   # 命中：物理上只存一份

    comp = zstd.compress(data, level=10)
    ext  = {"l0": "zst", "audio": "opus", "transcript": "zst", "doc": "zst"}[kind]
    rel  = f"{kind}/{raw_hash[:2]}/{raw_hash}.{ext}"
    abs_ = os.path.join(settings.archive_root, rel)

    os.makedirs(os.path.dirname(abs_), exist_ok=True)
    tmp = abs_ + ".tmp"
    with open(tmp, "wb") as f:
        f.write(comp)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, abs_)                                 # 同分区原子替换

    conn.execute("""INSERT INTO memory_blobs(hash, kind, storage_path, compression, mime,
                                             raw_size, size, ref_count, expires_at)
                    VALUES (?,?,?,?,?,?,?,1,?)
                    ON CONFLICT(hash) DO UPDATE SET
                        storage_path = excluded.storage_path,
                        compression  = excluded.compression,
                        size         = excluded.size,
                        ref_count    = memory_blobs.ref_count + 1,
                        state        = 'live',
                        purged_at    = NULL""",
                 (raw_hash, kind, rel, "zstd", mime, len(data), len(comp),
                  iso_in_days(settings.ttl_orphan_grace_days) if ttl_days else None))
    return raw_hash
```

**两级目录 `l0/ab/abc…`**：单目录放 10 万文件会让 NTFS/ext4 的目录遍历变慢，按哈希前缀分 256 个子目录。

#### 6.10.2 材料登记与按需取回

```python
def put_document(conn, *, user_id, title, source, text, mime="text/plain") -> str:
    """把一份材料整篇写入 L0：一份材料一个文件，不分块。"""
    data = text.encode("utf-8")
    # 先按“未验证”的最长档落下，验证后由回收任务提前释放
    h = put_blob(conn, data, kind="l0", mime=mime,
                 ttl_days=settings.doc_ttl_unverified_days)
    doc_id = new_id("d")
    conn.execute("""INSERT INTO memory_documents(
                        doc_id, user_id, title, source, mime, blob_hash,
                        char_count, raw_size, compressed_size, expires_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                 (doc_id, user_id, title, source, mime, h, len(text),
                  len(data), blob_size(conn, h),
                  iso_in_days(settings.doc_ttl_unverified_days)))
    log_event(conn, action="L0_ARCHIVE", actor="cli",
              detail={"doc_id": doc_id, "hash": h, "chars": len(text)})
    return doc_id


def restore_span(conn, *, entry_id: str, before: int = 500, after: int = 500) -> dict:
    """按条目取回原文区间 ± 上下文。只解压到内存，不落盘、不写回主库。"""
    row = conn.execute("""SELECT e.doc_id, e.l0_offset, e.l0_length,
                                 d.blob_hash, d.state
                            FROM memory_entries e
                            JOIN memory_documents d ON d.doc_id = e.doc_id
                           WHERE e.entry_id = ?""", (entry_id,)).fetchone()
    if row is None or row["doc_id"] is None:
        raise ValueError("L0_NOT_FOUND")
    if row["state"] == "purged":
        raise ValueError("L0_PURGED")

    text = read_blob(conn, row["blob_hash"]).decode("utf-8")
    lo = max(0, row["l0_offset"] - before)
    hi = min(len(text), row["l0_offset"] + row["l0_length"] + after)

    conn.execute("""UPDATE memory_documents
                       SET restore_count = restore_count + 1, last_restored_at = ?
                     WHERE doc_id = ?""", (now_iso(), row["doc_id"]))
    log_event(conn, entry_id=entry_id, action="L0_RESTORE", actor="api")
    return {"doc_id": row["doc_id"], "text": text[lo:hi],
            "offset": row["l0_offset"], "length": row["l0_length"],
            "context_before": before, "context_after": after}
```

两处与 v2.0 的差别：

1. **不写临时文件**：一条 L1 对应的区间通常只有几百字，直接返回文本更简单；只有“导出整篇”才落盘（`export_document(doc_id)`）。
2. **带上下文窗口**：只给区间本身，人往往看不懂指代；前后各 500 字是为了让“这句话在说什么”可判断。

#### 6.10.3 回收：四条触发

L0 整篇存带来的唯一实质代价是**回收粒度 = 材料粒度**。用四条触发把上限压住：

| 触发 | 条件 | 动作 | 可逆 |
|---|---|---|---|
| 引用归零 | `live_ref_count = 0` | 进回收站 → 7 天后删 | 是 |
| 无人再需要 | 引用它的条目全部 `archived/superseded` 且已硬归档 | 进回收站 → 删 | 是 |
| 硬 TTL（未验证档） | `expires_at` 到期（默认 730 天） | 删（`pin/anchor` 引用者豁免） | 是 |
| 提前释放（已验证档） | 活跃条目全部已核对 且 材料龄 ≥ 180 天 | 删 | 是 |
| 瘦身 | 活引用 ≤ 2、材料龄 ≥ 180 天、原文 >> 被引用区间 | 重写为区间摘录 | **否** |

```python
RECLAIM_TTL_SQL = """(
    expires_at < :cutoff_long
    OR (created_at < :cutoff_verified
        AND live_ref_count > 0
        AND NOT EXISTS (SELECT 1 FROM memory_entries e
                         WHERE e.doc_id = memory_documents.doc_id
                           AND e.status IN ('active','completed','pending_merge')
                           AND e.verified_at IS NULL)))
   AND state <> 'purged'
   AND NOT EXISTS (SELECT 1 FROM memory_entries e
                    WHERE e.doc_id = memory_documents.doc_id
                      AND (e.pin=1 OR e.anchor=1))"""


def reclaim_documents(conn, *, dry_run=False) -> dict:
    """每晚随维护管道执行，返回四类回收的统计。"""
    conn.execute("""UPDATE memory_documents SET live_ref_count = (
                        SELECT count(*) FROM memory_entries e
                         WHERE e.doc_id = memory_documents.doc_id
                           AND e.status IN ('active','completed','pending_merge'))""")

    stats = {}
    stats["zero_ref"] = _trash(conn, "live_ref_count = 0 AND state <> 'purged'", dry_run)
    # 到期分两档：未验证按长档，全部已核对则按短档提前释放
    stats["ttl"] = _trash(conn, RECLAIM_TTL_SQL, dry_run)
    stats["shrunk"] = _shrink_idle(conn, dry_run)
    return stats
```

**瘦身（`_shrink_idle`）**：当材料满足 `live_ref_count ≤ SHRINK_LIVE_REF`、`created_at` 早于 `SHRINK_MIN_AGE_DAYS`、且 `char_count > 20 × 被引用区间总长` 时，把它重写为“仅保留被引用区间（前后各 200 字）”的新 blob：

```text
解压原文 → 按 offset/length 截取保留段 → 按原序拼接（段间插 …
…）
        → zstd 重压 → 新哈希 → 更新 blob_hash / compressed_size
        → state='shrunk' → 写 L0_SHRINK 日志（原哈希、新哈希、丢弃字符数）
```

代价必须写明：

| 项 | 说明 |
|---|---|
| **不可逆** | 未被引用的原文永久丢弃，没有回收站（否则瘦身无意义） |
| 指针要重算 | 拼接后偏移变化，需同事务内更新所有 `l0_offset/l0_length` |
| 不该默认开 | 合同、病历、法律文本这类证据型材料应把 `SHRINK_ENABLED` 关掉，只靠 TTL |

**容量水位**：磁盘使用率 > `DISK_WARN_PCT`（默认 80%）时，维护任务自动收紧——TTL 判定提前 30 天、瘦身阈值从 2 条放宽到 5 条，`/healthz` 返回 `degraded: storage`。

#### 6.10.4 对外函数

| 函数 | 作用 |
|---|---|
| `put_blob` / `read_blob` / `blob_size` / `blob_rel` | Blob 基本操作 |
| `put_document(...) -> doc_id` | 材料整篇落盘 + 登记 |
| `restore_span(entry_id, before, after)` | 按条目取回区间 + 上下文（内存返回） |
| `export_document(doc_id)` | 导出整篇到 `cache/restore/`，供人工整理 |
| `reclaim_documents()` | 四条触发回收（引用归零 / 全员归档 / TTL / 瘦身） |
| `_shrink_idle()` | 瘦身主逻辑，支持 `dry_run` 预演 |
| `scan_orphans()` / `dedup_scan()` | 双向对账、历史重复文件清理 |
| `stats()` | 冷归档体积、压缩比、各 kind 占比、活引用分布 |

### 6.11 decay.py

#### 6.11.1 参数与数学口径

权重 `weight` 的物理含义是“当前浮现概率”，取值 0～1，初值 1.0。每日按类别乘一个系数，并受 `importance` 调制：

```
m_eff = 1 − (1 − m_base) × (1.6 − 1.2 × importance)

importance = 0.0 → 衰减加速 1.6×
importance = 0.5 → 原速（1.0×）
importance = 1.0 → 衰减减速至 0.4×
```

| 类别 | `m_base`（日乘数） | 半衰期 | 降至 0.1 所需天数 | 说明 |
|---|---|---|---|---|
| `task` | 0.95 | ≈ 13.5 天 | **≈ 45 天** | 任务过期最快，避免旧任务占位 |
| `decision` | 0.995 | ≈ 138 天 | ≈ 460 天 | 决策是长期事实，但技术选型会变 |
| `knowledge` | 0.99 | ≈ 69 天 | ≈ 229 天 | 知识稳定，仍会过时 |
| `preference` | 0.99 | ≈ 69 天 | ≈ 229 天 | 强烈建议 `pin`，否则定期回访 |
| `fiction_inspiration` | 0.995 | ≈ 138 天 | ≈ 460 天 | 灵感衰减慢，宁多勿少 |

> **口径纠正**：S1 写“task ×0.95，~20 天 weight=0.1”，算术上不成立——`0.95^20 ≈ 0.358`，到 0.1 需 `ln0.1 / ln0.95 ≈ 44.9` 天。本方案按 45 天记，并把“多少天进入软归档”改为由配置文件推导而非硬编码，避免再次出现文档与实现不符。若确实需要 20 天，应把 `decay_task` 调为 `0.89`（`0.89^20 ≈ 0.098`）。

#### 6.11.2 软归档与硬归档阈值

| 阶段 | 条件 | 动作 | 可逆性 |
|---|---|---|---|
| 权重衰减 | 每日 | `weight *= m_eff`，下限 0.01 | 可逆（命中回升） |
| 软归档 | `weight ≤ 0.10` 且 `pin=0` 且 `anchor=0` 且 `status IN (active, completed)` | `status='archived'`，FTS 转入 history | 可逆（`restore_entry`） |
| 硬归档 | `status='archived'` 且 `weight ≤ 0.05` 且距 `last_accessed_at`（无则 `created_at`）≥ 180 天 | 复制到 `memory_entries_archive`，删除主表行 | 半可逆（归档表可查，需人工导回） |
| L0 清理 | `expires_at < now − 宽限期` | 移回收站 → 删除 | 宽限期内可逆 |

#### 6.11.3 每日管道（7 步）

```python
def run_daily_maintenance(db_path: str, *, dry_run: bool = False) -> dict:
    conn = get_db_connection(db_path)
    stats = {}
    with flock("var/maintenance.lock"):          # 防重叠执行
        stats["decay"]        = step_decay(conn)
        stats["soft_archive"] = step_soft_archive(conn)
        stats["hard_archive"] = step_hard_archive(conn)
        stats["l0_archive"]   = step_l0_sweep(conn)      # 补齐未落盘的 L0 + 压缩
        stats["ttl_purge"]    = step_ttl_purge(conn, dry_run=dry_run)
        stats["log_cleanup"]  = step_log_cleanup(conn)
        stats["orphan_gc"]    = step_orphan_gc(conn, dry_run=dry_run)
        stats["reconcile"]    = step_reconcile(conn)      # 双 FTS 与 blob 对账
    return stats
```

**步骤 1：权重衰减**

```sql
UPDATE memory_entries
   SET weight = max(0.01, min(1.0,
                 weight * (1 - (1 - :m) * (1.6 - 1.2 * importance)))),
       updated_at = :now
 WHERE status IN ('active','completed')
   AND pin = 0 AND anchor = 0
   AND category = :category;
```

按类别执行 5 次，`:m` 取对应 `decay_*`。整轮只写**一条**汇总日志：

```sql
INSERT INTO memory_logs(action, new_value, actor) VALUES ('DECAY', :agg, 'scheduler');
-- :agg = {"task": {"rows": 812, "avg_drop": 0.041}, "knowledge": {...}, ...}
```

> 这是“不逐行记权重变化”的落地方式：既留了可观测性，又避免日志表被日常衰减淹没。

**步骤 2：软归档**

```sql
UPDATE memory_entries
   SET status='archived', updated_at=:now
 WHERE status IN ('active','completed')
   AND pin=0 AND anchor=0
   AND weight <= :soft_threshold;
```

触发器会自动把它从 `memory_fts_active` 挪到 `memory_fts_history`，因此归档后仍可被 `mode=history` 检索到——**归档不等于丢失**，这是双 FTS 结构的核心收益。

**步骤 3：硬归档**

```sql
-- 3.1 快照到归档表（列清单显式列出，避免 AS SELECT * 的列序风险）
INSERT INTO memory_entries_archive(
    row_id, entry_id, user_id, session_id, memory_group_id, root_id, version_no,
    predecessor_id, superseded_by, category, type, l1_summary, tokenized_content,
    l1_hash, doc_id, l0_offset, l0_length, chunk_index, l0_state, media_id,
    source, confidence, importance, status, pin, anchor, weight, access_count,
    valid_from, valid_to, created_at, updated_at, last_accessed_at,
    archived_at, archive_reason)
SELECT row_id, entry_id, user_id, session_id, memory_group_id, root_id, version_no,
       predecessor_id, superseded_by, category, type, l1_summary, tokenized_content,
       l1_hash, doc_id, l0_offset, l0_length, chunk_index, l0_state, media_id,
       source, confidence, importance, status, pin, anchor, weight, access_count,
       valid_from, valid_to, created_at, updated_at, last_accessed_at,
       :now, 'weight_low'
  FROM memory_entries
 WHERE status='archived' AND weight <= :hard_weight
   AND coalesce(last_accessed_at, created_at) < :idle_cutoff;

-- 3.2 删除主表行（触发器自动清 FTS）
DELETE FROM memory_entries
 WHERE status='archived' AND weight <= :hard_weight
   AND coalesce(last_accessed_at, created_at) < :idle_cutoff;
```

> 两个语句必须同事务。否则“归档表已写、主表未删”会导致下轮重复插入（`entry_id` 无唯一约束时不报错，产生重复快照）。`dry_run` 只执行 3.1 的 `SELECT count(*)`。

**步骤 4：L0 补齐与压缩**

遍历 `doc_id IS NULL` 但存在遗留原文（v1 的 `l0_raw_content`）的条目，逐条 `put_document()` 后回填 `doc_id`、`l0_offset=0`、`l0_length=char_count`。批量 200 条/事务，避免长事务持锁。

**步骤 5：TTL 清理**（见 6.10.3）

```sql
SELECT d.doc_id, d.blob_hash, b.storage_path
  FROM memory_documents d JOIN memory_blobs b ON b.hash = d.blob_hash
 WHERE d.expires_at < :grace_cutoff
   AND NOT EXISTS (SELECT 1 FROM memory_entries e
                    WHERE e.doc_id = d.doc_id AND (e.pin=1 OR e.anchor=1));
```

**步骤 6：日志分级清理**

```sql
-- 高频低价值日志：保留 90 天
DELETE FROM memory_logs
 WHERE ts < :d90 AND action IN ('FIELD_DIFF','RECALL_HIT','DECAY','UPDATE','INSERT');

-- 语义日志：保留 730 天后压成月汇总（而非直接删）
DELETE FROM memory_logs WHERE ts < :d730 AND action IN ('SUPERSEDE','ARCHIVE','HARD_ARCHIVE');
```

**步骤 7：孤儿与对账**

```
a) memory_blobs 中 state='orphan' 且超宽限期 → 删文件、置 purged
b) 磁盘上存在但 memory_blobs 无记录 → 移入 archive/_orphan/，写 WARN 日志
c) memory_blobs 有记录但文件缺失 → 标记 state='missing'（新增状态），告警
d) FTS 行数与主表不一致 → 对该条目做一次 delete+insert 修复
e) 同 group 多 active → 保留 version_no 最大者，其余置 superseded 并告警
```

### 6.12 asr_adapter.py 与 media_ingest.py

#### 6.12.1 统一转写接口

两个后端实现同一个协议，上层不感知差异：

```python
Segment = TypedDict("Segment", {"start": float, "end": float,
                                 "speaker": str | None, "text": str})

class AsrBackend(Protocol):
    def transcribe(self, audio_path: str, *, lang: str | None,
                   model: str | None) -> tuple[list[Segment], dict]: ...
    # 返回 (segments, meta)，meta 含 model / lang / speaker_count / duration
```

| 后端 | 选型 | 适用 | 关键参数 |
|---|---|---|---|
| 本地 | `faster-whisper`（CTranslate2） | VPS 无外网、隐私敏感、批量离线 | `model=medium`、`compute_type=int8`、`vad_filter=True`、`beam_size=5` |
| 云端 | OpenAI Whisper API / 兼容接口 | 本机 CPU 弱、追求速度 | `model=whisper-1`、分段上传 ≤ 25 MB |

**选择建议**：本机开发用云端（省 CPU），VPS 生产用 `faster-whisper small/medium + int8`（4 核可跑，1 小时音频约 8～20 分钟）。配置项 `ASR_PROVIDER=local|openai`。

**统一后处理**：`segments` 按 60 秒窗口合并为段落，保留 `[mm:ss]` 时间戳前缀，拼成转写全文——这样 L0 里既有全文，也能按时间定位回放。

#### 6.12.2 媒体入库流程

```python
def ingest_media(conn, *, user_id, file_path, media_type="audio",
                 transcribe=True, group_id=None) -> dict:
    # 1. 校验：大小、MIME（ffprobe 实测而非信任扩展名）、时长上限
    # 2. 转码：ffmpeg -ac 1 -ar 16000 -c:a libopus -b:a 24k  → 体积降 85%+
    # 3. 冷存：put_blob(kind='audio', ttl=ttl_audio_days) → 得 blob_hash
    # 4. media_id：插入 memory_media(transcript_state='pending')
    # 5. 转写（可同步或入队）：asr.transcribe → segments → 全文
    # 6. 全文 put_blob(kind='transcript') → transcript_blob
    # 7. 全文走 ingest.extract_and_store(source='recording', media_id=...)
    # 8. 回填 memory_media.entry_id / transcript_state='done' / transcribed_at
    # 9. 失败：transcript_state='failed' + error_message，条目不入库（避免污染）
    ...  # 这里只列流程；实现属于非必要功能（音频），不在主计划内
```

**分块策略**：转写全文可能很长（1 小时会议 ≈ 1.5 万字 ≈ 6 块）。每块独立提炼，但 `media_id` 相同、`group_id` 相同，从而在看板上可“按录音聚合”查看。

**幂等**：同一 `blob_hash` 重复上传 → 直接返回既有 `media_id`，不重复转写（用 `memory_media` 按 `blob_hash` 查）。

### 6.13 dashboard.py

```python
class Handler(BaseHTTPRequestHandler):
    server_version = "Tinderbox/2.0"

    # 装饰器链：鉴权 → 限流 → 参数校验 → 异常映射 → JSON 响应
    @api("GET", "/api/search")
    def search(self, q, mode="active", include_archive=False, source=None,
               media=False, top_k=10, cursor=None): ...

    def _auth(self) -> bool:
        if not settings.api_token:
            return self.client_address[0] in ("127.0.0.1", "::1")   # 无 token 时仅本机
        return hmac.compare_digest(
            self.headers.get("Authorization", "").removeprefix("Bearer ").strip(),
            settings.api_token)
```

- `ThreadingHTTPServer(daemon_threads=True)`，每请求独立连接，`finally` 中关闭；
- 上传走流式落盘到 `var/upload/`，超过 `upload_max_mb` 立即 413，不读入内存；
- 静态看板由同一进程在 `/` 托管（见 11 章），避免 `file://` 的 `Origin: null` 问题。

### 6.14 mcp_server.py

MCP 服务是 API 的另一层皮，**不重复业务逻辑**，只做参数转换与错误映射：

```python
@server.tool()
def store_memory(user_id: str, content: str, category: str = "knowledge",
                 source: str = "conversation", media_id: str | None = None,
                 valid_from: str | None = None, valid_to: str | None = None) -> dict:
    """直接写入一条记忆（不经过 LLM 提炼）。"""
    return storage.insert_memory(get_db_connection(settings.db_path),
                                 user_id=user_id, l1_summary=content,
                                 category=category, source=source,
                                 media_id=media_id,
                                 valid_from=valid_from, valid_to=valid_to)
```

错误映射：`ValueError("EMPTY_L1")` → MCP `isError=True` + `"内容为空"`；`StaleVersion` → 提示“版本已变化，请重新读取”。


### 6.15 concept_index.py —— 概念挂靠

> 原则：**人搭骨架，机器挂靠**。层级和父子由人定，机器只回答“这条记忆该挂在哪个已有概念下”。

#### 6.15.1 挂靠流程

```text
新条目（或批量重算）
  │
  ├─ 1. 候选：与该条目向量最接近的 k 个概念质心（k=5）
  ├─ 2. 置信度：margin = 最高分 − 次高分        ← 不是绝对余弦
  ├─ 3. 闸门：margin ≥ CONCEPT_MARGIN
  │        ├─ 是 → 写入 memory_entry_concepts(assigned_by='vector', confidence=margin)
  │        └─ 否 → 不挂，进「待归类」队列（人看板处理）
  └─ 4. 提议：一批条目彼此高度相似、且都没有归属
           → 建一个 kind='proposed' 的概念，等人命名
```

#### 6.15.2 为什么用 margin 不用绝对余弦

2026-10-26 用 25 条真实记忆、9 个概念做了一次标定（bigram TF-IDF 替身，未装嵌入模型）：

| 指标 | 实测 |
|---|---|
| accuracy@1（最近质心） | **52%**（随机基线 11%） |
| 命中时余弦 | 0.018 ～ 0.210，中位 0.090 |
| 错配时余弦 | 0.022 ～ 0.106，中位 0.054 |
| 结论 | 两组分布**大幅重叠**，任何绝对阈值都分不开 |

改用“与第二名的差距”：

| 取 margin 最高的 | 门槛 | 准确率 |
|---|---|---|
| 前 10%（2 条） | ≥ 0.102 | **100%** |
| 前 20%（5 条） | ≥ 0.053 | 80% |
| 前 50%（12 条） | ≥ 0.029 | 83% |
| 全部 25 条 | — | 52% |

**三条可直接采用的结论**：

1. **绝对阈值不可移植**。随手写“0.78 以上算同一概念”是错的——分数尺度由表示决定：TF-IDF 落在 0.02～0.21，嵌入模型通常落在 0.6～0.9。阈值必须**在同一表示下标定**。
2. **置信度用 margin**。绝对分数几乎不区分对错，而“比第二名高出多少”区分得很清楚。
3. **弱表示下精度与覆盖率不可兼得**。要 90% 精度，只能自动挂 8%——这就是为什么机器只能“挂靠”，不能“建网”。

#### 6.15.3 落库与回退

| 场景 | 处理 |
|---|---|
| 挂错 | 人改 `assigned_by='manual'` 覆盖，原记录进审计 |
| 概念合并 | `UPDATE memory_entry_concepts SET concept_id=?`，保留冲突清单 |
| 概念拆分 | 新建子概念，把部分成员改挂过去 |
| 重算 | `maintenance recompute-concepts`，按 `is_seed` 判据重跑，输出 diff 供确认 |

#### 6.15.4 验收

| 指标 | 门槛 | 达不到怎么办 |
|---|---|---|
| 挂靠 precision | ≥ 0.95 | 收紧 margin，牺牲覆盖率 |
| 挂靠 coverage | ≥ 0.60 | **换表示**（嵌入模型），而不是继续调阈值 |

这条很重要：**调阈值只能在曲线上滑动，换模型才能把曲线抬起来**。

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

### 7.3 排序优先级（分层）

`score` 之上还有**层级**，用于表达“无论分数多低都必须靠前”的语义：

| tier | 条件 | 说明 |
|---|---|---|
| 3 | `pin=1` | 用户显式置顶 |
| 2 | `anchor=1` | 锚定记忆，不受衰减 |
| 1 | `category='decision'` | 决策优先展示 |
| 0 | 其他 | 按 `score` 排序 |

排序键：`ORDER BY tier DESC, score DESC, created_at DESC`。

### 7.4 检索 SQL

```sql
WITH cand AS (
    -- 候选召回：只查 FTS，用 rowid 与主表对齐；多取 3 倍，为后续过滤留余量
    SELECT f.rowid                          AS row_id,
           bm25(memory_fts_active, 0.0, 1.0) AS bm25_raw
      FROM memory_fts_active f
     WHERE memory_fts_active MATCH :match_expr
     ORDER BY bm25_raw
     LIMIT :candidate_budget
)
SELECT e.entry_id, e.l1_summary, e.category, e.status, e.weight,
       e.memory_group_id, e.version_no, e.superseded_by, e.l0_state, e.media_id,
       e.created_at, e.valid_from, e.valid_to,
       c.bm25_raw
  FROM cand c
  JOIN memory_entries e ON e.row_id = c.row_id
 WHERE e.user_id = :user_id
   AND e.status = :status_filter          -- 'active' / 'superseded' / 'archived'
   AND (:source     IS NULL OR e.source    = :source)
   AND (:media_only = 0     OR e.media_id IS NOT NULL)
 ORDER BY c.bm25_raw;
```

**实现注意（三点）**

1. `pow()` 需要 SQLite 编译时开启 `SQLITE_ENABLE_MATH_FUNCTIONS`，Python 官方发行版不一定带，不能依赖。
2. `bm25()` 只能出现在“直接查询该 FTS 表”的语句里，放在标量子查询里一边求 `max` 一边过滤，会整表**扫描两遍**，10 万条时明显变慢。
3. 因此采用**三段式**：SQL 只做候选召回（`LIMIT candidate_budget`）→ Python 过滤与打分 → 排序取 `top_k`。**预算随过滤条件放大**：无过滤时 `top_k × 3`；带 `source`/`media_id`/`user_id` 过滤时 `top_k × 6`——固定 3 倍在多重过滤下可能剩不到 `top_k` 条。多取 3 倍是为了让 `user_id/status/source` 过滤后仍有足够候选。

```python
def _score(row, query_max, half_life_days):
    s_rel = row["rel_raw"] / query_max if query_max > 0 else 1.0
    age_d   = (now_utc() - parse_iso(row["created_at"])).total_seconds() / 86400
    s_rec   = 0.5 ** (age_d / half_life_days)
    return settings.w_rel * s_rel + settings.w_rec * s_rec + settings.w_weight * row["weight"]
```

### 7.5 召回降级策略

| 情况 | 处理 |
|---|---|
| `MATCH` 语法错误（用户输入含 `"` `*` `:` 等） | 全部 token 加引号并转义，`build_match` 已保证；仍失败则回退 `LIKE '%词%'` |
| `AND` 命中 < 3 条 | 自动改 `OR` 重查，结果按命中 token 数加权 |
| 分词后 token 为空（纯标点/停用词） | 返回空结果 + `hint: "查询无可检索词"`，不打 DB |
| 查询词含英文/数字 | 英文按词、数字整体保留；`unicode61` 对拉丁文本本就可分 |
| 冷启动（库为空） | 返回空数组 + `hint: "记忆库为空"` |

### 7.6 分组去重

`hybrid` 模式下同一 `group_id` 可能同时命中 active 与 history 两条。默认 `group_dedup=True`：每组只保留 tier/score 最高的一条，但响应中附带 `siblings: [{entry_id, version_no, status}]`，前端可展开看整条链。`group_dedup=False` 时全部返回（供“时间线视图”使用）。

### 7.7 访问回写

命中即视为“使用”，回写必须在**响应返回后**异步执行，避免拖慢读请求：

```sql
UPDATE memory_entries
   SET access_count = access_count + 1,
       last_accessed_at = :now,
       weight = min(1.0, weight + :boost)
 WHERE entry_id = :entry_id AND pin = 0 AND anchor = 0;

INSERT INTO memory_logs(entry_id, action, actor) VALUES (:entry_id, 'RECALL_HIT', 'api');
```

> `RECALL_HIT` 日志量最大（每次检索 × top_k 条）。它受 90 天保留策略约束，且可配置为“仅记录 top 1”以进一步降噪（`settings.log_recall_top_only`）。

### 7.8 性能预算

| 规模 | 目标 | 手段 |
|---|---|---|
| 1 万条 | p95 < 30 ms | 索引 1、3；候选 50 |
| 10 万条 | 混合 p95 < 300 ms（缓存命中 < 120 ms）；纯 FTS < 150 ms | 候选上限 50；RRF 融合；查询向量 LRU；`mmap_size` |
| 100 万条 | p95 < 600 ms（不承诺） | 需引入分区或外部检索，超出本方案范围 |


### 7.4 对话开头的主动浮现

新对话开始时，系统要**主动**给几条记忆，而不是等人问。这是“记忆库”与“搜索框”的分界线。

**打分（纯本地、确定、可解释）**：

```text
score = 0.50 × weight + 0.30 × 新鲜度
      + 0.25  若 pin 或 anchor
      + 0.15  若该链改过 ≥2 版且现行版已 >30 天（可能已过时，该复查）
      + 0.30  若该条目有未裁决冲突
```

**必须去重，且按话题去重**：同一话题只出一条；与已选条目字面重合（Jaccard > 0.55）的也跳过。

> 第一版按“版本组”去重，结果浮现出三条同义句（一个话题的三个段落各自成了组）。**浮现错一条，用户就不再信这个功能**——宁可少给。

**每条都要带“为什么是它”**：`权重 1.00；新鲜度 0.85；改过 4 版且已 60 天，可能该复查`。人看不懂为什么浮现，就不会去看它。

**返回结构**：

```python
{"memories": [...], "pending_conflicts": 2, "provisional": 16, "total": 34}
```

`pending_conflicts` 与 `provisional` 单独返回：前者提醒“有 2 件事等你裁决”，后者提醒“还有 16 条没精修”——**都是状态，不该混进记忆列表**。

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

### 8.4 存储回收与容量水位

L0 整篇存带来的唯一实质代价：**回收粒度 = 材料粒度**。一份文档拆出 20 条记忆，一年后 19 条沉底，只要还有 1 条活着，整份原文就得留着。四条触发（详见 6.10.3）：

| 触发 | 条件 | 动作 | 可逆 |
|---|---|---|---|
| 引用归零 | `live_ref_count = 0` | 回收站 → 7 天后删 | 是 |
| 无人再需要 | 引用它的条目全部 `archived/superseded` 且已硬归档 | 回收站 → 删 | 是 |
| 硬 TTL（未验证档） | `expires_at` 到期（默认 730 天） | 删（`pin/anchor` 豁免） | 是 |
| 提前释放（已验证档） | 活跃条目全部已核对 且 材料龄 ≥ 180 天 | 删 | 是 |
| 瘦身 | 活引用 ≤ 2、材料龄 ≥ 180 天、原文远大于被引用区间 | 重写为区间摘录 | **否** |

**稳态存储的上限因此是三个确定的数**：

```text
稳态 L0   ≈ 日摄入材料量 × DOC_TTL_DAYS（去重后）
稳态音频   ≈ 日录音小时 × 0.0108 GB/h × AUDIO_TTL_DAYS
主库       ≈ 活跃条目数 × 2 KB + 归档表（3 年后裁剪）
```

三样都有天花板，**不随使用年限线性膨胀**——这才是“整篇存”能成立的前提：不是靠省，是靠边界清楚。

**水位策略**：磁盘使用率 > 80% 时自动收紧（TTL 提前 30 天判定、瘦身阈值放宽到 5 条活引用），`/healthz` 返回 `degraded: storage`，上传接口开始拒收大文件。

### 8.5 容量估算

以 10 万条记忆、平均 L1 250 字、平均每条原文 3 000 字为例：

| 项目 | 单条/单位 | 总量 | 备注 |
|---|---|---|---|
| `memory_entries` 行 | ≈ 0.9 KB | ≈ 90 MB | 含 `tokenized_content` |
| 18 个索引 | — | ≈ 36 MB | 主表的 30% |
| FTS 索引 | ≈ 0.6 KB | ≈ 60 MB | 含倒排与位置 |
| `memory_logs` | — | ≈ 40 MB | 90 天滚动 |
| **主库合计** | — | **≈ 255 MB** | 符合 G3（≤ 400 MB）；含向量 30 MB |
| L0 文本（zstd ≈3.5:1） | ≈ 1.2 KB | ≈ 120 MB | 一份材料被 5～20 条共享 |
| 向量（int8, 1024 维） | 1 KB | ≈ 30 MB | 只存活跃条目（约 3 万条），归档即删 |
| 音频（opus 24 kbps） | 10.8 MB/小时 | 视录音量 | 180 天 TTL 控制上限 |

> L0 与条目不是 1:1：平均一份材料产出 5～20 条 L1，所以“10 万条记忆”通常只对应 1～2 万份材料，实际 L0 体积低于上表。

**录音容量公式**：`容量 ≈ 日录音小时 × 0.0108 GB × 180 天`。日录 2 小时 ≈ 3.9 GB。


#### 8.6 实现约定（demo 已验）

| 约定 | 理由 |
|---|---|
| **`reclaim()` 默认 `dry_run=True`** | 删原文不可逆。要真删必须显式 `--apply`——顺手调用不该能毁数据 |
| 保留档按**材料内是否有核对过的条目**判定（180 / 730 天） | 一条被核对，说明整份材料被读过；没核准的按长档留 |
| 释放字节按**唯一 blob** 计 | 同一段文字被多份材料共用（去重），按材料累加会把 2 KB 算成 4 KB |
| 回收必须**幂等** | 第二次跑命中 0 份；cron 天天跑，不能越跑越乱 |
| 缺列自动补（`ensure_columns`） | 旧库不该因为加了一列就重建；`connect()` 与 `init_db()` 都会补 |

**实测**（`run_maintenance.py`）：三份材料分别 200 天已核对 / 800 天未核对 / 400 天未核对 →
dry-run 命中 2 份且不改数据；真执行删 2 份、释放 2,004 字节、剩 1 份（400 天未核对，正确保留）；
无孤儿、无负引用；再跑一次命中 0（幂等）。

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

## 10 MCP 工具规范

### 10.1 工具清单

| # | 工具 | 动作 | 关键参数 | 返回 |
|---|---|---|---|---|
| 1 | `store_memory` | 改 | `user_id, content, category, source, media_id, valid_from, valid_to` | `{entry_id, group_id, version_no}` |
| 2 | `query_memories` | 改 | `user_id, query, mode, include_archive, top_k, source, media` | `[{entry_id, l1_summary, score, status, version_no}]` |
| 3 | `extract_and_store` | 改 | `user_id, text, source` | `{inserted: n, items: [...]}` |
| 4 | `transcribe_and_store` | 加 | `user_id, file_path, media_type, group_id` | `{media_id, entry_ids, duration_sec}` |
| 5 | `list_conflicts` | 加 | `user_id, limit` | `[{conflict_id, old, new, relation, confidence, suggestion}]` |
| 6 | `resolve_conflict` | 加 | `conflict_id, resolution, merged_summary` | `{state, affected_entries}` |
| 7 | `restore_l0` | 加 | `entry_id, before, after` | `{text, offset, length, context}` |
| 8 | `get_history_chain` | 加 | `group_id` | `{group, entries[], timeline[]}` |
| 9 | `supersede_memory` | 保留 | `old_entry_id, new_content, expected_version_no` | `{entry_id, version_no}` |
| 10 | `active_context` | 保留 | `user_id, limit` | 按 tier 排序的“当前上下文包” |
| 11 | `get_stats` | 加 | `user_id` | 统计摘要 |
| 12 | `health_check` | 加 | — | `{db, fts, disk_free_gb, schema_version}` |

**设计约束**

- 全部工具**只做薄封装**，不重复实现业务逻辑；
- `query_memories` 默认 `mode="active"`、`top_k=10`、`touch=False`（避免 AI 的试探性检索污染权重）；
- **分工要写死**：`active_context` 用于「AI 每次对话都自动注入」——它 `touch=False`，因为那不是人想看；`query_memories` 由 AI 或人显式调用，`touch=True`，因为它代表一次真实检索。若 AI 是主要消费者，权重会天然偏向人的使用模式，这是**已知偏差**，不是 bug——排查权重异常时先看这个。
- 工具描述（docstring）必须写明“何时该用”，这是模型选择工具的唯一依据；
- 所有工具返回**可直接 JSON 序列化**的 dict，不返回 ORM/Row 对象。

### 10.2 工具描述范例（决定模型是否会正确调用）

```python
@server.tool()
def query_memories(user_id: str, query: str, mode: str = "active",
                   include_archive: bool = False, top_k: int = 10) -> list[dict]:
    """检索长期记忆。

    何时使用：需要回忆过去的决定、偏好、项目约定或已确认的事实时。
    何时不要用：查询当前对话里已经出现过的内容（那是浪费一次工具调用）。

    mode 选择：
      - "active"（默认）：找当前仍然有效的记忆。
      - "history"：用户问"以前是怎么做的""为什么改掉了"时使用，
        会返回已被取代或已归档的旧版本。
      - "hybrid"：不确定记忆是否已失效时使用，两种都查。
    """
```

### 10.3 MCP 配置

```json
{
  "mcpServers": {
    "tinderbox": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "E:\\记忆库",
      "env": {
        "DEEPSEEK_API_KEY": "sk-xxx",
        "DB_PATH": "memory.db",
        "ARCHIVE_ROOT": "archive",
        "API_TOKEN": ""
      }
    }
  }
}
```

> 用 `-m mcp_server` 而非裸脚本路径，可让 `src/` 包正确解析；`cwd` 必须设为项目根，否则相对路径的 `archive/` 会落到客户端工作目录。

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

### 11.3 技术约束

- 单文件 HTML + 原生 ES 模块，不引入构建链（保持“双击/书签即用”）；
- 不引入 React/Vue：页面状态简单，原生足以支撑，且避免 npm 依赖进入运维面；
- 图表用内联 SVG 手绘（环形图/柱图），不引第三方图表库；
- 所有用户内容渲染走 `textContent`，禁止 `innerHTML`（防 XSS）；确需富文本时用白名单函数；
- 深色/浅色跟随 `prefers-color-scheme`，配色用 CSS 变量。

### 11.4 人工裁决的交互约定

冲突页是唯一一个**必须有人在场**的操作。约定如下：

| 约定 | 理由 |
|---|---|
| 卡片同时展示**新旧两条全文**，不做截断 | 裁决的依据是语义，看不全就没法判 |
| 判定理由原样展示，**包括另一判定器的意见** | 两个判定器意见不一致时，人需要看见分歧（6.9.6） |
| 三个按钮对应 `supersede` / `keep_both` / `ignore`，**没有默认值、没有回车提交** | 这是不可逆操作，必须显式点 |
| 点完立即从列表移除，页头计数同步减一 | 候选池要肉眼可见地变短 |
| 只展示 `state='open'`，已裁决的进历史（可回溯） | 待办列表不该混入已完成项 |

**展示示例**（真实产出）：

```text
[override] 置信 0.95
旧：六月改为A供单品豆、B供拼配豆的双轨方案——因为单品豆客单价高用好的豆子…
新：九月最终定A独家供应、B只做备用——因为双轨管理太麻烦，每次进货对两个账本出错率高
九月新方案取代六月双轨方案，明确改变决定（另一判定器：complement 0.60）
[旧作废，新版接管]  [两条都留]  [忽略]
```

括号里那句是关键：**规则判定器认为“只是补充”，模型认为“是覆盖”，并集机制把它挂起了**——但把分歧如实交给裁决人，而不是假装两边一致。

**接口**：`GET /api/conflicts` 取待裁决列表（含新旧摘要与理由），`POST /api/conflicts/resolve` 提交 `{conflict_id, resolution}`，返回 `{ok, state}`。

## 12 Obsidian 导出与 Git

### 12.1 文件布局

```
vault/
├── 2026/
│   └── 10/
│       ├── mem-9f2c1a7b3d40.md
│       └── mem-c3d4e5f6078a.md
├── _groups/
│   └── g-7f3a2b11c9de.md          # 版本组索引（时间线 + 全部版本链接）
├── _media/
│   └── m-4a1b.md                  # 音频摘要 + 附件链接
└── _meta/
    ├── index.md                   # 自动生成的分类索引
    └── stats.md                   # 每日统计快照
```

**为什么按年月分目录**：单目录几千个 `.md` 会让 Obsidian 侧边栏与搜索明显变慢。文件名保持 `entry_id` 不变（稳定、可被 WikiLink 引用），层级只影响展示。

### 12.2 Frontmatter

```yaml
---
entry_id: mem-9f2c1a7b3d40
schema_version: "2.22.0"
user_id: pelican
category: decision
status: active
confidence: high
importance: 0.8
source: conversation
media_id:
group_id: g-7f3a2b11c9de
root_id: mem-a1b2c3d4e5f6
version_no: 3
predecessor: "[[mem-b2c3d4e5f6a7]]"
successor:
valid_from: 2026-10-20
valid_to:
l0_state: live
l0_expires: 2027-10-20
created_at: 2026-10-20T02:11:09.512Z
updated_at: 2026-10-20T02:11:09.512Z
tags:
  - memory/decision
  - mem/v3
---
```

正文：

```markdown
# 部署方式定为 systemd

部署方式定为 systemd，不再使用 nohup；原因是重启后可自动恢复且便于日志归集。

## 版本链

- 上一版：[[mem-b2c3d4e5f6a7]]（v2）
- 本版：v3（当前有效）
- 组索引：[[g-7f3a2b11c9de]]

## 相关记忆

（由 conflict_guard 判为 complement 的条目，自动列出）
```

文件顶部不写 `# 标题`？Obsidian 习惯用 frontmatter `title` 或首行 H1。这里用首行 H1 作标题（人可读），并在 frontmatter 不重复 `title`，避免双标题。

### 12.3 音频记忆的导出

音频本身**不进 Vault**（体积大、Git 不适合存二进制）：

```markdown
---
entry_id: mem-4a1b2c3d4e5f
source: recording
media_id: m-7c8d9e0f1a2b
duration_sec: 1832
transcript_state: done
---
# 季度评审会议：确定 Q4 目标是"稳定优先"

（L1 摘要）

## 转写全文（前 500 字）

> [00:00] 今天主要过一下 Q4 的三个目标……
> [02:14] 我的意见是稳定性优先于新功能……

全文见记忆库：`/api/detail?id=mem-4a1b2c3d4e5f`（L0 / 音频可在线回放）

## 附件

[会议录音（需登录记忆库回放）](http://127.0.0.1:8765/api/media/m-7c8d9e0f1a2b?exp=…&sig=…)
```

签名链接带过期时间，因此导出时**不写死签名 URL**，而写一个跳转链接 `/go/media/{media_id}`，由服务端现签——避免“导出时有效、几天后 403”的坏体验。

### 12.4 异步 Git 队列

```
写入事务提交
   │
   ├─ exporter.enqueue(entry_id) → 追加一行到 var/export_queue.jsonl
   │      （append + flush，进程崩溃最多丢最后一行）
   │
   └─ exporter 后台线程（每 60 s 或攒够 50 条）
          ├─ 读取队列 → 生成/更新 .md → 幂等覆盖
          ├─ git add <受影响文件>
          ├─ git commit -m "memory: <n> 条更新 (<first_id>…)"
          ├─ git push（失败重试 3 次：1 s / 5 s / 30 s）
          └─ 成功后截断队列；失败保留并告警，下轮重试
```

**幂等**：文件名与内容均以 `entry_id` 为准，重复生成只会覆盖同一文件，不会产生副本。若 `entry_id + version_no` 相同而内容不同（不该发生），以库内为准覆盖，并在日志记 `EXPORT_CONFLICT`。

**不阻塞主事务**：`enqueue` 只做一次文件追加，耗时 < 1 ms。S1 的“导出到 Obsidian 后 git push”是同步的，会让一次记忆写入卡住数秒（网络 + Git 索引），S2 明确要求改异步，本方案照此执行。

### 12.5 导出内容裁剪

| 字段 | 是否导出 | 理由 |
|---|---|---|
| `l1_summary` | 是 | 核心可读内容 |
| `tokenized_content` | 否 | 机器产物，人不需要 |
| `weight / access_count` | 否 | 内部调度量，导出会造成“频繁变动”的 Git 噪声 |
| `doc_id / l0_offset` | 否 | 内部索引 |
| `status / version_no / group_id` | 是 | 支撑双链与历史阅读 |
| `valid_from / valid_to` | 是 | 事实有效期对人有用 |
| 软删除条目 | 是（标 `status: archived`） | Vault 是“完整档案”，不是“只看最新” |
## 13 部署与运维

> **范围**：本机或一台 VPS 单机部署即可。13.4 的 systemd 单元、13.6 的可观测性属于**非必要**——一个人用一个记忆库，先能跑起来、能备份、能恢复，就是全部要求。反向代理、TLS、监控是多人协作才需要的东西。



### 13.0 部署形态与 `user_id` 的关系

**先分清两件事**：`user_id` 记录的是**所有者身份**，不是“程序跑在哪”。

| 形态 | 谁能访问 | `user_id` | 需要补什么 |
|---|---|---|---|
| **本机**（默认） | 只有本机进程 | `owner` | 无。绑 `127.0.0.1`，令牌只防同机误连 |
| **单用户 VPS** | 互联网上持有令牌的人 | **仍是 `owner`** | 反向代理 + TLS + 令牌轮换 + 备份；`user_id` 不变 |
| **多用户** | 多个人，各看各的 | 每人一个 | **当前不支持**——需要真用户体系、每查询过滤、跨用户索引 |

**所以放到云上要改的不是 `user_id`，而是四件事**：

1. **绑定地址**：`127.0.0.1` → 只监听反代的内网口，**不要**直接 `0.0.0.0`；
2. **TLS**：tokens 与数据都走明文 HTTP 是不可接受的，必须反代终结 TLS；
3. **令牌**：从“防误连”升级为“真正的凭证”——轮换、不进版本库、不写进日志；
4. **备份**：单机跑可以不备份，云上不备份等于随时丢数据（见 13.5）。

**一个必须承认的边界**：单令牌 = 单身份。把令牌给两个人，系统分不出谁是谁——
没有 per-user 审计、没有按人隔离。这正是“多用户不支持”的具体含义，
不是忘了做，是**没做之前不要假装有**。

### 13.1 目录结构

```
E:\记忆库\                          # 或 /opt/tinderbox
├── memory.db                       # 主库（WAL 会伴生 -wal / -shm）
├── .env / .env.example
├── requirements.txt
├── mcp_server.py                   # MCP 入口（薄封装）
├── dashboard.py                    # HTTP 入口（薄封装）
├── dashboard_v2.html               # 看板（由 dashboard.py 同源托管）
├── archive/                        # 冷存储根（必须独立于备份盘策略考虑）
│   ├── l0/<hh>/<hash>.zst          # L0 原文（按哈希前 2 位分桶）
│   ├── audio/<hh>/<hash>.opus      # 音频
│   ├── transcript/<hh>/<hash>.zst  # 转写全文
│   ├── _trash/                     # 回收站（7 天后真删）
│   └── _orphan/                    # 无 DB 记录的孤儿文件（人工确认后删）
├── vault/                          # Obsidian 仓库（git 工作区）
├── cache/restore/                  # L0 临时解压目录（定期清空）
├── var/
│   ├── maintenance.lock
│   ├── media.lock
│   ├── export_queue.jsonl
│   ├── userdict.txt                # jieba 自定义词典
│   └── logs/                       # 应用日志（按日滚动）
├── src/
│   ├── config.py  db.py  textproc.py
│   ├── storage.py  ingest.py  retriever.py  decay.py
│   ├── version_chain.py  conflict_guard.py  archive_manager.py
│   ├── asr_adapter.py  media_ingest.py  exporter.py  llm.py
│   ├── maintenance.py
│   └── migrations/
│       ├── __init__.py
│       └── v2_0_0.py
└── tests/
```

**分区建议**：`archive/` 与 `memory.db` 最好在**不同物理盘**；若只有一块盘，至少保证 `archive/` 不与系统盘共享——冷存储是容量增长最快、最怕写满的部分。

### 13.2 依赖清单

```txt
# requirements.txt（精确锁版本）
openai==1.51.0            # DeepSeek 兼容 OpenAI 协议
python-dotenv==1.0.1
jieba==0.42.1             # 必须锁版本：分词口径变化会导致 FTS 需要全量重建
zstandard==0.23.0
mcp==1.2.0
faster-whisper==1.0.3     # 可选：ASR_PROVIDER=local 时需要
# 系统依赖：ffmpeg / ffprobe（媒体转码与探测）
```

| 依赖 | 引入原因 | 备注 |
|---|---|---|
| `jieba` | S1 标“预留”，S2 改为实依赖 | 版本锁定；词典变更需重建 FTS |
| `zstandard` | L0 压缩，比 gzip 快 3～5 倍、压缩率更高 | 压缩级别 10 为速度/体积平衡点 |
| `faster-whisper` | 本地 ASR | 首次运行会下载模型（`small` ≈ 480 MB） |
| `ffmpeg` | 转码 opus、探测真实时长与编码 | 系统包，不进 pip |
| `sqlite-vec` | 向量 KNN 索引 | 以扩展方式加载；缺失则检索降级为纯 FTS |
| `onnxruntime` + `transformers` | 本地嵌入推理（仅用 tokenizer，不含 torch） | bge-m3 int8 ONNX 约 0.6 GB，常驻内存约 1.2 GB |

### 13.3 本地开发

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env       # 填入 DEEPSEEK_API_KEY

python -m src.maintenance init    # 建库、建表、建触发器、自检
python -m src.maintenance seed    # 可选：写入 20 条演示数据
python dashboard.py               # 启动 API :8765
# 浏览器打开 http://127.0.0.1:8765
```

### 13.4 VPS 生产部署（systemd）

S1 用 `nohup` 启动，进程崩溃不会自愈、日志无轮转、重启后不自动拉起。S2 要求改 systemd，配置如下：

```ini
# /etc/systemd/system/tinderbox.service
[Unit]
Description=Tinderbox API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=memory
WorkingDirectory=/opt/tinderbox
EnvironmentFile=/opt/tinderbox/.env
ExecStart=/opt/tinderbox/.venv/bin/python dashboard.py
Restart=always
RestartSec=3
StandardOutput=append:/var/log/tinderbox/api.log
StandardError=append:/var/log/tinderbox/api.err.log

# 加固
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/tinderbox /var/log/tinderbox
LimitNOFILE=8192

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/tinderbox-maintenance.service
[Unit]
Description=Tinderbox daily maintenance

[Service]
Type=oneshot
User=memory
WorkingDirectory=/opt/tinderbox
EnvironmentFile=/opt/tinderbox/.env
ExecStart=/opt/tinderbox/.venv/bin/python -m src.maintenance daily
```

```ini
# /etc/systemd/system/tinderbox-maintenance.timer
[Unit]
Description=Run Tinderbox maintenance daily at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true          # 关机错过则开机补跑

[Install]
WantedBy=timers.target
```

启用：

```bash
systemctl daemon-reload
systemctl enable --now tinderbox.service
systemctl enable --now tinderbox-maintenance.timer
systemctl list-timers tinderbox-maintenance.timer
```

> **为什么用 timer 而不是 crontab**：`Persistent=true` 解决“凌晨关机导致漏跑”；`systemd` 原生接管日志与失败重试；`systemctl status` 能直接看到上次执行结果。S1 的 crontab 写法在 VPS 上仍可用，但缺少补跑与可观测性。

**反向代理（可选，需要外网访问时）**

```nginx
server {
    listen 443 ssl http2;
    server_name memory.example.com;

    client_max_body_size 200m;              # 与 upload_max_mb 对齐

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;            # 转写可能较慢
    }
}
```

> 暴露到公网前必须：① 设置非空 `API_TOKEN`；② 开启 HTTPS；③ 在反代层再限流一次；④ 关闭 `/metrics` 的公网访问。

### 13.5 备份与恢复

**备份对象与策略**

| 对象 | 方式 | 频率 | 保留 |
|---|---|---|---|
| `memory.db` | `sqlite3 memory.db ".backup '<dst>'"`（在线一致快照） | 每日 | 7 日 + 4 周 |
| `archive/` | `rsync -a --delete` 或 `rclone sync` | 每日 | 4 周（版本化） |
| `vault/` | 已在 Git 远端，无需额外备份 | — | 永久 |
| `.env` | 加密后离线保存 | 变更时 | — |

**禁止**直接 `cp memory.db`：WAL 模式下会得到缺少 `-wal` 内容的损坏副本。必须用 `.backup` 或先 `PRAGMA wal_checkpoint(TRUNCATE)`。

```bash
#!/usr/bin/env bash
# scripts/backup.sh
set -euo pipefail
STAMP=$(date +%F)
DEST=/backup/tinderbox/$STAMP
mkdir -p "$DEST"
sqlite3 /opt/tinderbox/memory.db ".backup '$DEST/memory.db'"
rsync -a --delete /opt/tinderbox/archive/ "$DEST/archive/"
sqlite3 "$DEST/memory.db" "PRAGMA integrity_check;"   # 备份可用性校验
find /backup/tinderbox -maxdepth 1 -type d -mtime +28 -exec rm -rf {} +
```

**恢复演练（每季度一次）**

1. 停服务；2. 用备份覆盖 `memory.db` 与 `archive/`；3. `python -m src.maintenance check`（外键 + FTS + 版本组一致性）；4. 抽 10 条记忆做检索与 L0 恢复；5. 恢复服务。

### 13.6 可观测性

| 指标 | 来源 | 告警阈值 |
|---|---|---|
| 磁盘剩余 | `/healthz` | < 10 GB 警告，< 3 GB 停止上传 |
| WAL 大小 | 文件大小 | > 200 MB（说明检查点失效） |
| LLM 失败率 | 应用日志 | 5 分钟内 > 20% |
| 检索 p95 | `/metrics` | > 500 ms 持续 10 分钟 |
| 对账不一致数 | `maintenance daily` | > 0 即告警 |
| TTL 清理失败 | 同上 | 任一失败即告警 |

**日志格式**：单行 JSON，字段 `ts, level, event, entry_id, request_id, elapsed_ms, detail`，便于 `jq` 与日志系统解析。**禁止**把 `l1_summary` 全文写进错误日志（隐私）。

### 13.7 日常运维命令

```bash
python -m src.maintenance init            # 建库
python -m src.maintenance migrate         # 迁移到最新 schema
python -m src.maintenance check           # 完整性自检
python -m src.maintenance daily           # 手动跑一次每日管道（cron 入口）
python -m src.maintenance daily --dry-run # 只打印将发生什么，不改数据
python -m src.maintenance reconcile       # DB ↔ 磁盘 ↔ FTS 对账并修复
python -m src.maintenance reindex         # 全量重建三个 FTS（分词口径变更后必做）
python -m src.maintenance stats           # 打印容量与分布
python -m src.maintenance vacuum          # PRAGMA optimize + VACUUM
```


### 13.8 本地 / 云端双兼容

**只做两种形态，第三种明确不做。**

| 形态 | 含义 | 代价 | 状态 |
|---|---|---|---|
| **A 代码兼容** | 同一份代码，本机或云上都能跑，只改配置 | 小 | **已具备**（13.0） |
| **B 只读副本** | 本机是唯一写者，定期把快照推到云，供手机只读 | 中（约半天） | **规划** |
| **C 双向同步** | 两边都能写，改完互相同步 | 大 | **不做**（理由见 13.8.1） |

#### 13.8.1 为什么不做双向同步

三条硬理由，一条产品理由：

| # | 理由 | 说明 |
|---|---|---|
| 1 | **文件同步会毁库** | 把 `memory.db` 放进 OneDrive/iCloud，WAL 会撕裂。SQLite 官方明令禁止 |
| 2 | **多写者没有跨机锁** | SQLite 的锁是文件级、单机的；两台机器同时写，后写的直接覆盖 |
| 3 | **删除无法传播** | 没有墓碑（tombstone），下次同步会把删掉的条目“复活” |
| 4 | **它必然“有感”** | 我们的原则是“不自动赢，挂起给人看”（6.9）。双向同步意味着偶尔要你点几下裁决 |

第 4 条是产品层面的：**如果用户要的是“改完自动到处都是、从不问我”，那不是这套设计能给的**——
得换 CRDT，代价是数据模型推倒重来（版本链、冲突裁决全部失效）。**宁可没有，也不做一个半吊子的。**

#### 13.8.2 B 的做法：同步操作日志，不是同步数据库文件

```sql
CREATE TABLE memory_changes(
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,  -- 本地单调序号
    origin     TEXT NOT NULL,                      -- 哪台机器（设备 id）
    entity     TEXT NOT NULL,                      -- entry / document / relation / concept
    entity_id  TEXT NOT NULL,
    op         TEXT NOT NULL,                      -- upsert / archive / delete
    payload    TEXT NOT NULL,                      -- JSON
    created_at TEXT NOT NULL,
    UNIQUE(origin, origin_seq)
);
```

**流程**：本机写完 → 追加一条日志 → `sync push` 把 `seq > last_pushed` 的日志推到云 →
云端按 `origin_seq` 顺序重放，重建一个**只读副本**。

| 规则 | 理由 |
|---|---|
| 同一个 `origin` 的日志串行重放 | 顺序不会乱 |
| 云端只读，不接受写 | 避免多写者，也就避开了理由 2 |
| 删除写墓碑，不物理删 | 否则下次推送会“复活” |
| 数据模型无需改动 | 已有随机 ID（不撞）、只追加、版本链 |

#### 13.8.3 为什么这套能落地

不是新建机制，而是**复用已有的四样东西**：

| 已有 | 用途 |
|---|---|
| 全局随机 ID | 两台机器各自新建不会撞 |
| 只追加、不物理删 | 日志天然可重放 |
| 版本链 | “谁覆盖谁”已有语义 |
| 冲突挂起 + 人工裁决 | 万一云上收到冲突，直接走现成流程 |

#### 13.8.4 什么时候做

**先不做。** 等 demo 多跑几轮、确认真有“在外面看”的需求，再花那半天。
在那之前，`Markdown 镜像`（5.22）就是最朴素的双端方案：导出 → 传到哪都能读。

## 14 安全与隐私

### 14.1 威胁模型

| 威胁 | 场景 | 对策 |
|---|---|---|
| 未授权访问 API | 端口暴露到公网且无 token | 默认绑 `127.0.0.1`；非空 `API_TOKEN` 才允许非回环访问 |
| 路径穿越 | `media_id` 构造 `../../etc/passwd` | 媒体一律按 DB 中的 `storage_path` 读取，不接受用户传入路径 |
| 签名链接重放 | 泄漏的回放地址被长期使用 | 签名含 `exp`（默认 10 分钟）；服务端不缓存 |
| 上传炸弹 | 200 MB 压缩包解压后 10 GB | 只接受白名单 MIME（ffprobe 实测）+ 时长上限 + 不解压用户输入 |
| SQL 注入 | 检索词含 `'` 或 FTS5 语法 | 全部参数化；`build_match` 对 token 加引号并转义 |
| 记忆投毒 | 通过 MCP 写入恶意/错误记忆 | `confidence` 与 `source` 可见；冲突走 `pending_merge`；导出保留原文供复核 |
| 隐私外泄 | LLM 调用把私密内容发给第三方 | 可配置 `LLM_DISABLE=true` 走纯规则提炼（降级模式） |
| 日志泄漏 | 错误日志写入全文 | 日志只写 ID 与长度，不写正文 |

### 14.2 数据分级与保留

| 级别 | 内容 | 保留 | 备注 |
|---|---|---|---|
| 敏感 | 音频原文件 | 180 天 | 到期自动清理，`anchor` 可豁免 |
| 较敏感 | L0 原文 | 365 天 | 同上 |
| 一般 | L1 摘要 | 长期 | 硬归档后仍保留 |
| 元数据 | 日志 | 90 天 / 730 天分级 | 见 6.11.3 |

### 14.3 配置安全

- `.env` 权限 `600`，加入 `.gitignore`；
- `API_TOKEN` 与 `SIGN_SECRET` 用 `openssl rand -hex 32` 生成，不复用；
- 启动时若 `bind_host != 127.0.0.1` 且 `api_token` 为空 → **拒绝启动**并打印原因（失败即关闭，而非静默运行）。

### 14.4 上传接口加固

```python
ALLOWED = {"audio/mpeg","audio/wav","audio/x-wav","audio/ogg","audio/opus",
           "audio/mp4","audio/webm","video/mp4"}

def validate_upload(stream, declared_mime: str, declared_size: int) -> dict:
    if declared_size > settings.upload_max_mb * 1024 * 1024:
        raise ApiError(413, "PAYLOAD_TOO_LARGE")
    if declared_mime not in ALLOWED:
        raise ApiError(415, "UNSUPPORTED_MEDIA")
    # 落盘到 var/upload/<uuid>.bin 后，用 ffprobe 实测真实格式与时长
    # 实测 MIME 与声明不符 → 415；时长 > 4 小时 → 400
    ...
```

## 15 数据迁移（v1 → v2.1）

### 15.1 迁移总览

> **前提**：v2.0 只存在于文档、从未落过库。因此不存在 v2.0→v2.1 的数据迁移，本章只处理 **v1（已实现的草稿版）→ v2.1**。

```text
v1 库（content 单层、单 FTS、无版本组、原文留在主表）
  │
  ├─ 0. 预检：版本号、行数、磁盘空间（需 ≥ 当前库 × 3）
  ├─ 1. 备份：.backup 到 backup/pre_v2_<timestamp>.db
  ├─ 2. 建新结构：新表 / 新列 / 新索引 / 新触发器（旧触发器先删）
  ├─ 3. 数据回填：content → l1_summary；生成 l1_hash；分词写 tokenized_content
  ├─ 4. 版本组重建：无版本关系的条目各自成组；有 superseded_by 的串成链
  ├─ 5. 材料归并：按来源把条目聚成 memory_documents，回填 doc_id 与区间
  ├─ 6. FTS 全量重建：删除旧 FTS，按 status 分别灌入 active / history
  ├─ 7. 旧结构清理：drop memory_fts、drop 无用列、建兼容视图
  ├─ 8. 校验：外键 / 行数 / 抽样检索 / 版本组一致性
  └─ 9. 记录版本：memory_schema_meta.schema_version = '2.20.0'
```

第 5 步是 v2.1 新增、也最容易出错：v1 的原文是“每条一份”，v2.1 要求“一份材料一份”。归并优先级：① 同一 `session_id` 的连续条目；② 同一 `source` 且文本互为子串；③ 都不满足则一条条目单独成一份材料——**宁可多留一份，不要错误合并**。

三条顺序约束（与 v2.0 相同，重申）：先撤旧触发器后建新触发器；先灌数据后建触发器；版本号最后写。

### 15.2 关键步骤的 SQL

**步骤 2：加列（SQLite 允许带常量默认值的 ADD COLUMN）**

```sql
ALTER TABLE memory_entries RENAME COLUMN content TO l1_summary;   -- 3.25+，保留数据
ALTER TABLE memory_entries ADD COLUMN l1_hash          TEXT;
ALTER TABLE memory_entries ADD COLUMN tokenized_content TEXT NOT NULL DEFAULT '';
ALTER TABLE memory_entries ADD COLUMN memory_group_id   TEXT;
ALTER TABLE memory_entries ADD COLUMN root_id           TEXT;
ALTER TABLE memory_entries ADD COLUMN version_no        INTEGER NOT NULL DEFAULT 1;
ALTER TABLE memory_entries ADD COLUMN predecessor_id    TEXT;
ALTER TABLE memory_entries ADD COLUMN valid_from        TEXT;
ALTER TABLE memory_entries ADD COLUMN valid_to          TEXT;
ALTER TABLE memory_entries ADD COLUMN source            TEXT NOT NULL DEFAULT 'api';
ALTER TABLE memory_entries ADD COLUMN importance        REAL NOT NULL DEFAULT 0.5;
ALTER TABLE memory_entries ADD COLUMN media_id          TEXT;
ALTER TABLE memory_entries ADD COLUMN doc_id            TEXT;
ALTER TABLE memory_entries ADD COLUMN chunk_index       INTEGER;
ALTER TABLE memory_entries ADD COLUMN l0_offset         INTEGER;
ALTER TABLE memory_entries ADD COLUMN l0_length         INTEGER;
ALTER TABLE memory_entries ADD COLUMN l0_state          TEXT NOT NULL DEFAULT 'none';
ALTER TABLE memory_entries ADD COLUMN access_count      INTEGER NOT NULL DEFAULT 0;
ALTER TABLE memory_entries ADD COLUMN updated_at        TEXT;
```

> **`row_id` 的处理**：v1 以 `entry_id TEXT` 为主键，表本身有隐式 `rowid`；为获得 `AUTOINCREMENT` 语义与完整约束，v2 必须重建表（`CREATE new → INSERT SELECT → DROP old → RENAME`）。因此上面用占位列演示顺序，实际执行顺序为：先 `ALTER RENAME COLUMN` 改名，再建 `memory_entries_new`，用 `INSERT INTO ... SELECT` 搬数据（同时计算 `l1_hash`、`tokenized_content`），最后 `DROP` 旧表并 `RENAME`。分词必须**在 Python 侧**完成（SQLite 无 jieba），因此该步是 `SELECT 批量 → Python 处理 → executemany` 的循环，每批 500 行。

**步骤 4：版本组重建**

```python
# 1) 先为所有条目建独立组
for row in rows:
    gid = new_id("g")
    conn.execute("INSERT INTO memory_groups(group_id, root_id, user_id, topic, category)"
                 " VALUES (?,?,?,?,?)", (gid, row["entry_id"], row["user_id"],
                                         make_topic(row["l1_summary"]), row["category"]))
    conn.execute("UPDATE memory_entries SET memory_group_id=?, root_id=? WHERE entry_id=?",
                 (gid, row["entry_id"], row["entry_id"]))

# 2) 处理已有的 supersede 链：有 superseded_by 的，沿链回溯到根，统一 group
def rebuild_chain(entry_id):
    chain, cur = [], entry_id
    while cur is not None:
        chain.append(cur)
        cur = conn.execute("SELECT superseded_by FROM memory_entries WHERE entry_id=?",
                           (cur,)).fetchone()["superseded_by"]
    root = chain[0]
    gid  = group_of(root)
    for i, eid in enumerate(chain, start=1):
        conn.execute("""UPDATE memory_entries
                           SET memory_group_id=?, root_id=?, version_no=?,
                               predecessor_id=?  WHERE entry_id=?""",
                     (gid, root, i, chain[i-2] if i > 1 else None, eid))
```

**步骤 5：材料归并**

```python
def merge_documents(conn):
    rows = conn.execute("""
        SELECT coalesce(session_id, 'solo-' || entry_id) AS key, user_id, source,
               group_concat(entry_id) AS ids
          FROM memory_entries WHERE doc_id IS NULL
         GROUP BY key, user_id, source""").fetchall()
    for g in rows:
        text = build_source_text(conn, g["ids"])          # 按 created_at 拼原文
        doc_id = put_document(conn, user_id=g["user_id"], title=auto_title(text),
                              source=g["source"], text=text)
        for eid, off, ln in align_spans(text, g["ids"]):
            conn.execute("""UPDATE memory_entries
                               SET doc_id=?, l0_offset=?, l0_length=? WHERE entry_id=?""",
                         (doc_id, off, ln, eid))
```

`align_spans()` 用字符串定位把每条 L1 映射回原文区间；定位失败（原文被截断或改写）时回填 `(0, len(text))` 并记 `MIGRATE_SPAN_UNRESOLVED`，供人工复核。

**步骤 6：FTS 全量重建**

```sql
DELETE FROM memory_fts_active;
DELETE FROM memory_fts_history;

INSERT INTO memory_fts_active(rowid, entry_id, tokenized_content)
SELECT row_id, entry_id, tokenized_content FROM memory_entries
 WHERE status='active' AND tokenized_content <> '';

INSERT INTO memory_fts_history(rowid, entry_id, tokenized_content)
SELECT row_id, entry_id, tokenized_content FROM memory_entries
 WHERE status IN ('superseded','archived') AND tokenized_content <> '';

DROP TABLE IF EXISTS memory_fts;           -- v1 的旧单表索引
```

> **FTS 不能增量迁移**：分词器从 `unicode61` 直索引改为 jieba 预分词，索引内容口径完全变了。任何“保留旧索引 + 只补新行”的做法都会让新旧数据检索行为不一致，必须全量重建。重建 10 万条约需 2～4 分钟（含 jieba 分词），应在维护窗口执行。

**步骤 7：兼容视图（给未升级的旧调用方）**

```sql
CREATE VIEW IF NOT EXISTS memory_entries_v1 AS
SELECT entry_id, user_id, session_id, category, type,
       l1_summary AS content,          -- 旧字段名映射
       confidence, status, pin, anchor, weight,
       superseded_by, created_at, last_accessed_at
  FROM memory_entries;
```

### 15.3 迁移脚本骨架

```python
# src/migrations/v2_0_0.py
def migrate(db_path: str, *, dry_run: bool = False) -> dict:
    report = {"steps": []}

    with connect(db_path) as conn:
        check_version(conn, from_="1.0.0", to="2.24.0")     # 不匹配直接抛
        backup(conn, db_path)                              # 步骤 1

        with write_tx(conn):
            create_v2_objects(conn)                        # 步骤 2（新表/索引）
            drop_v1_triggers(conn)                         # 旧触发器先撤，避免迁移中误写 FTS
            report["steps"].append("ddl")

        backfill_l1_and_tokens(conn, batch=500)            # 步骤 3
        rebuild_groups(conn)                               # 步骤 4
        archive_legacy_l0(conn)                            # 步骤 5
        rebuild_fts(conn)                                  # 步骤 6
        drop_legacy(conn)                                  # 步骤 7
        create_v2_triggers(conn)                           # 触发器在数据灌完后建，避免百万次触发
        verify(conn)                                       # 步骤 8
        set_version(conn, "2.24.0")                         # 步骤 9
    return report
```

**关键顺序约束**

| 顺序 | 原因 |
|---|---|
| 先撤旧触发器，后建新触发器 | 否则回填 `tokenized_content` 时，旧触发器会按错误口径写 FTS |
| 先灌数据，后建触发器 | 触发器在批量插入时逐行执行，10 万行会显著拖慢迁移 |
| FTS 重建在 tokenized 回填之后 | 否则索引到空串 |
| 版本号最后写 | 中途失败时版本号仍为 1，可重跑（迁移脚本必须幂等） |

### 15.4 回滚

```bash
systemctl stop tinderbox
cp backup/pre_v2_20261025T0300.db memory.db
rm -f memory.db-wal memory.db-shm
systemctl start tinderbox
```

迁移脚本在任何步骤抛错时自动 `ROLLBACK` 当前事务并保留备份文件，**不做自动降级**（自动降级容易二次损坏）。若已部分提交，按上面的备份覆盖回滚。

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

### 16.2 评估指标与统计口径

| 指标 | 定义 | 采集方式 |
|---|---|---|
| Recall@10 | 查询集中相关条目出现在前 10 的比例 | 人工标注集 + 离线脚本 |
| 误归档率 | 归档后仍被人工标记为“应保留”的比例 / 归档总数 | 抽样 100 条人工复核 |
| 冲突数 | `state='open'` 的 `memory_conflicts` 数量 | SQL 统计 |
| 裁决分布 | `supersede` / `merge` / `keep_both` / `ignore` 占比 | SQL 统计 |
| Token 节省 | `Σ(l1_summary 字数) / Σ(L0 字数)`，与“全文入 prompt”对比 | 按周统计 |
| 冷归档体积 | `Σ memory_blobs.size where kind='l0'` | `/api/stats` |
| 压缩比 | `Σ raw_size / Σ size` | 同上 |

### 16.3 验收清单

- [ ] `python -m src.maintenance check` 全绿
- [ ] T1～T12 全部通过
- [ ] T13 在 10 万条造数下达标
- [ ] 看板 5 个核心页面可交互，无控制台报错
- [ ] MCP 12 个工具在 Cline 中可列出、可调用、错误可读
- [ ] Obsidian 导出 100 条后 Git 正常提交，WikiLink 可跳转
- [ ] 迁移演练在 v1 副本上完成一次，回滚验证通过
- [ ] 备份恢复演练完成一次


### 16.2 评估集与指标（demo 已跑，样本很小）

**两层数据，用途不同**：

| 层 | 构造方式 | 衡量什么 | 偏差 |
|---|---|---|---|
| **自证集** | 查询词取自条目摘要里的特征词 | 检索链路通不通、索引对不对 | **乐观上界**：词就在摘要里，当然能找到 |
| **话题查询** | 直接用话题名（选址 / 菜单 / 豆子…） | 真实提问的形态 | 更接近实用，但样本只有 5 个 |

**实测**（23 条记忆 / 2 份材料）：

| 指标 | 值 |
|---|---|
| R@1 / R@5 / R@10（自证集） | 100% / 100% / 100% |
| MRR | 1.00 |
| 话题词命中 | 选址 0/5、菜单 1/4、豆子 4/5、成本 5/5、雨天 2/2 |

话题词那一行的低值不是 bug：**摘要里本来就不含「选址」二字**（写的是「首站放在大学城」）。这正是 6.6.4 说的长度偏置——LLM 精修后才会好转。

**冲突判定**（10 对人工标注，5 个 override 正例）：

| 判定器 | precision | recall | F1 | 三分类准确率 |
|---|---|---|---|---|
| 规则 | 0.67 | 1.00 | 0.80 | 60% |
| LLM | 0.80 | 1.00 | 0.89 | 70% |
| 并集 | 0.67 | 1.00 | 0.80 | 70% |

**这些数不能当验收线，理由有三**：

1. **样本太小**：只有 5 个正例，precision 的置信区间约 ±0.2，只能看趋势；
2. **自证偏差**：检索集是自证的，R@1=100% 不代表真实提问能命中；
3. **标签本身有争议**：10 对里有 3 对（改口↔调整说明、菜单↔成本、雨天↔止损）换个产品口径就会换标签。

**一条确定的系统错误值得记**：把「实测数据」当成了被「改口」覆盖的对象。

> 旧：跑了一周大学城之后，实际日均只有 34 杯 ｜ 新：所以改口：首站改到创业园区

按「同话题 + 变更标记」判定，这组会被判成 `override`——但**数据不是决策，不该被决策覆盖**。

**结论**：当前评估只能当**冒烟测试**（链路通不通、指标会不会跑），不能当验收。
16.1 的 T6（≥300 对标注、精确率 ≥0.85）仍是上线门槛，需要真实标注数据才能验。

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

### 17.2 P0 任务分解

| # | 任务 | 产出 | 验收 |
|---|---|---|---|
| 1.1 | 建 `db.py` 新 DDL + 6 触发器 + 自检 | `src/db.py`、`schema.sql` | `init` 成功，`check` 全绿 |
| 1.2 | `textproc.py`（分词/归一化/MATCH） | 模块 + 单测 | T1、T2 通过 |
| 1.3 | 改造 `storage.insert_memory`（Append-Only + 去重） | 函数 + 单测 | T10 通过 |
| 1.4 | 改造 `storage.supersede_memory`（事务 + 乐观锁 + 版本字段） | 函数 + 并发测试 | T5 通过 |
| 1.5 | 改造 `ingest.py`（输出 L1 + 分词 + `source`） | 模块 | 长文 3 块提炼正确 |
| 1.6 | 改造 `retriever.py`（active 模式 + 新公式 + 降级） | 模块 | T3、T4 通过 |
| 1.7 | 改造 `decay.py`（排除 pin/anchor + 参数化 + 汇总日志） | 模块 | dry-run 数字与手算一致 |
| 1.8 | API 鉴权 + CORS 收口 + 同源托管看板 | `dashboard.py` | T18 通过 |
| 1.9 | Git 异步队列 | `exporter.py` | 写入不阻塞（p99 < 50 ms） |
| 1.10 | 迁移脚本 + 在 v1 副本演练 | `migrations/v2_0_0.py` | T12 通过 |

### 17.3 里程碑判定

| 里程碑 | 判定条件 |
|---|---|
| M0（P0 完成） | 新版可以完全替代旧版跑通“写入→检索→导出”，中文召回率达标 |
| M1（P1 完成） | 归档与 TTL 管道连续跑 7 天无异常，冷归档体积与估算吻合 |
| M2（P2 完成） | 人工可独立完成“发现冲突→裁决→查看版本链”全流程 |
| 上线 | 备份/恢复演练通过，迁移回滚演练通过 |

### 17.4 优先级排序理由

S2 把优先级定为 P0～P4。v2.16 把范围收窄为 **P0～P2**，其余转入「非必要功能」（17.1）。以下是仍然成立的几条前移理由：

| 项 | S2 定级 | 本方案 | 理由 |
|---|---|---|---|
| `version_chain` 的字段与链写入 | P1（模块） | **P0** | `supersede_memory` 的事务化依赖 `memory_group_id/version_no/predecessor_id` 三列；字段与事务必须一次做完，否则要改两次 schema |
| `archive_manager.put_blob` | P1（模块） | **P0** | `insert_memory` 的 `doc_id` 外键指向 `memory_documents`，材料必须经 `put_document()` 落盘；写入路径一开始就得走它，否则后续补齐要重扫全库 |
| 向量检索 | P4（可选） | **非必要（未排期）** | 理论上它能解“字面不重合”的配对问题，但 30 条真实记忆上的实测没有证明自己（概念挂靠 50% vs bigram 50%，配对更差）。先不排期，等换了真模型再评 |


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


### 17.6 尚未实现清单（截至 2026-10-27）

按章节过一遍，只列“文档里有、代码里没有”的：

| 章节 | 缺口 | 性质 | 建议 |
|---|---|---|---|
| 9 | `/api/add`、`/api/all`、`/api/stats`、`/api/history`、`/api/archive/l0`、媒体接口 | demo 只实现了 7 个接口 | 手写入口（`/api/add`）优先，其余按需 |
| 10 | MCP 工具全章 | 集成层 | 非必要；用 Claude Desktop 时再补 |
| 11 | 仪表盘 / 全部 / 添加 / 音频 / 冷归档 / 统计 六个页面；**主动浮现未接看板** | UI | 浮现接入半天，其余按需 |
| 12 | Obsidian 导出 + Git 异步队列 | 非必要 | 已标非必要 |
| 13 | 生产部署：反向代理、TLS、systemd、监控 | 运维 | 上云前必做 |
| 13.8 | 同步 B（只读副本） | 新设计 | 半天，等确有需求再做 |
| 14 | 审计日志（谁改了哪条） | 安全 | 单用户可缓；多用户前必须 |
| 15 | 数据迁移的重活：`rebuild_chain`、`merge_documents` | 迁移 | 只有 v1 真在跑才需要 |
| 附录 A | 大量配置项在 demo 里是硬编码（阈值、权重、预算） | 工程化 | 上生产前集中到 `config` |

**已经不缺的**：存储、写入、提炼、检索、版本链、冲突、裁决、概念、浮现（库函数）、
存档镜像、回收、鉴权、维护 CLI、评估——这十二块都有可运行的实现与测试。

## 18 风险与对策

| # | 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|---|
| R1 | 分词口径变更导致检索结果漂移 | 中 | 高 | 锁定 jieba 版本；词典文件进 Git；变更时强制 `reindex` 并回归 T4 |
| R2 | LLM 提炼质量不稳（幻觉/过度概括） | 高 | 中 | `temperature=0`；L0 原文永久保留可复核；`confidence` 分级；冲突判定不自动执行 |
| R3 | LLM 成本超预期 | 中 | 中 | 相似度闸门先过滤（< 0.35 不调 LLM）；单块 max_tokens 上限；按周统计 Token |
| R4 | TTL 误删不可恢复 | 低 | 高 | 回收站 7 天；`pin/anchor` 豁免；`daily --dry-run` 预演；删除前写 `L0_PURGE` 完整日志 |
| R5 | `ref_count` 漂移导致误删共享文件 | 中 | 高 | 每日对账（6.11.3 步骤 7）；删除前二次校验是否仍有 `memory_documents`/`memory_media` 引用；孤儿先入 `_orphan/` |
| R6 | 磁盘写满导致库损坏 | 中 | 高 | 水位告警；写满时拒写而非半写；WAL 大小监控；`archive/` 独立分区 |
| R7 | FTS 与主表不一致 | 中 | 中 | 启动自检 + 每日行数对账 + 每周 `integrity-check` 与 `optimize` |
| R8 | 本地 ASR 太慢阻塞服务 | 中 | 中 | ASR 独立进程/队列；`media.lock` 串行；上传接口立即返回 `queued`，前端轮询进度 |
| R9 | 版本链在并发下分叉 | 低 | 高 | `BEGIN IMMEDIATE` + `UNIQUE(group_id, version_no)` + 乐观锁；T5 覆盖 |
| R10 | 迁移中途失败 | 中 | 高 | 必须备份；触发器后建；版本号最后写；脚本幂等；回滚演练 |
| R11 | 看板 XSS | 低 | 中 | 一律 `textContent`；CSP `default-src 'self'`；不放 CDN |
| R12 | 隐私内容进入第三方 LLM | 中 | 高 | `LLM_DISABLE` 降级模式；日志不写正文；可选本地模型替代 |
| R13 | 嵌入模型换代导致向量失效 | 中 | 中 | 更换 `EMBED_MODEL` 必须整体重建向量；把模型名与维度写进 `memory_schema_meta`，启动时比对，不一致直接拒绝启动 |
| R14 | 向量拖慢检索 | **高** | 中 | bge-m3 在 4 核 CPU 上编码一条查询约 80～150 ms，是 FTS 的 10 倍；对策：查询向量 LRU 缓存、写入异步补向量、检索设 400 ms 超时后单路返回 |
| R15 | 内存争用（ASR 与嵌入同时常驻） | 中 | 高 | faster-whisper small ≈ 0.5 GB + bge-m3 ≈ 1.2 GB，加 OS 已逼近 4 GB 机器上限；建议 8 GB 内存，或 ASR 用按需加载、不常驻 |

## 19 待确认决策

以下 7 项须在开工前确认，本方案已给默认值，**不确认即按默认执行**。

| # | 决策点 | 默认 | 备选 | 影响 |
|---|---|---|---|---|
| D1 | 主要检索语言 | 中文优先 | 中英并重 | 中英并重需在 `tokenize_index` 增加英文词干化，FTS 需两套列 |
| D2 | ASR 后端 | 生产 `faster-whisper small/int8`，开发用云端 | 全程云端 | 本地需 4 核 + 4 GB 可用内存；云端有单文件 25 MB 限制 |
| D3 | 部署位置 | 本地 Windows + 可选 VPS | 仅 VPS / 仅本地 | 仅本地时不需要 nginx 与 HTTPS，但 MCP 与看板同机 |
| D4 | L0 的写入时机 | **写入即落盘**（不等降级） | 先留主库 `l0_hot`，衰减后再落盘 | 写入即落盘省一列、省一次迁移；代价是首次写入多一次磁盘 IO（约 2 ms） |
| D5 | 冲突是否自动裁决 | **不自动**，`override` 仅标 `pending_merge` | 高置信度（≥0.9）自动 supersede | 自动裁决省人力但有误杀风险，不可逆 |
| D6 | 向量检索的优先级 | **已定**：进 P1 | — | v2.2 已落地，见 5.18 / 6.9.3 / 7.2 |
| D7 | 嵌入模型选型 | **已定**：本地 `bge-m3`（1024 维，int8 ONNX） | 云端 `/v1/embeddings` | 中文与多语言语义显著优于 small 档；代价是 1.2 GB 常驻内存与 80～150 ms 查询编码，已计入 2.3 G4 与 18 R15 |

---

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

## 附录 B 与原方案的差异与修订说明

### B.1 已执行的 S2「改」

| # | 原文要求 | 落地位置 |
|---|---|---|
| 1 | `content` → `l1_summary` | 5.4 |
| 2 | `memory_fts` → `memory_fts_active` + 新增 `memory_fts_history` | 5.12、5.14 |
| 3 | tokenizer 改为 jieba 分词写入 | 5.12、6.3 |
| 4 | 触发器仅在 `tokenized_content/status` 变化时重建 | 5.14 |
| 5 | `insert_memory` 改 Append-Only + 版本绑定 | 6.5.1 |
| 6 | `supersede_memory` 事务化 + 乐观锁 | 6.5.2 |
| 7 | 衰减 SQL 排除 `pin/anchor`，参数配置化 | 6.11.1 |
| 8 | L0 由 `SET …=NULL` 改为压缩冷归档 | 6.10.2 |
| 9 | 检索三模式 Active/History/Hybrid | 7.1 |
| 10 | 打分改为 BM25 × weight × recency | 7.2 |
| 11 | API 增加 `mode/source/media` 等过滤 | 9.3 |
| 12 | 所有 API 加 token 或绑 localhost；CORS 收紧 | 9.5、14.3 |
| 13 | Git push 异步队列 + 重试 | 12.4 |
| 14 | 部署从 `nohup` 改 systemd | 13.4 |
| 15 | Frontmatter 增加 source/media/group/version/status | 12.2 |

### B.2 已执行的 S2「加」

| # | 原文要求 | 落地位置 |
|---|---|---|
| 1 | `memory_groups`、`memory_media`、`memory_documents` 三表（S2 原名 `memory_l0_archive`，v2.1 合并为材料表） | 5.5、5.8、5.7 |
| 2 | `conflict_guard.py`、`version_chain.py`、`archive_manager.py` | 6.9、6.8、6.10 |
| 3 | `media_ingest.py`、`asr_adapter.py` | 6.12 |
| 4 | 音频上传/转写/回放 API | 9.3、9.4 |
| 5 | 历史链、冲突裁决、L0 恢复/清除 API | 9.3、9.4 |
| 6 | 对应 MCP 工具（4 个） | 10.1 |
| 7 | UI：模式切换、版本时间线、冲突页、音频页、冷归档页、统计页 | 11.1 |
| 8 | TTL 管道（7 步） | 6.11.3、8.1 |
| 9 | 哈希去重（多条目共享一份） | 5.6、6.10.1 |
| 10 | 中文召回率测试等 7 项测试 | 16.1 |

### B.3 保留的 S1 内容

| 内容 | 说明 |
|---|---|
| MCP 原生挂载 | 保留，工具从 5 个扩到 12 个 |
| Obsidian `.md` + WikiLink + Git | 保留，增加版本链双联与幂等 |
| 单文件 HTML 看板、事件委托 | 保留，改为同源托管 |
| 分块 2500/200 + 内容哈希去重 + 指数退避 | 保留，补按段落切分与降级策略 |
| `db.py/storage.py/ingest.py/retriever.py/decay.py` 五模块划分 | 保留，另拆出 `textproc.py`、`config.py` 与 5 个新模块 |
| 审计日志、冷归档条目表 | 保留，细化 action 枚举与保留策略 |
| SQLite + WAL + FTS5 + DeepSeek 技术选型 | 保留 |

### B.4 本方案补齐的细节

| # | 缺口 | 补齐内容 |
|---|---|---|
| 1 | 两稿均无 DDL，只有字段表 | 5 章给出可执行完整 DDL、6 个触发器 SQL、18 个索引 |
| 2 | 无状态机 | 3.4 给出 `status` 与 `l0_state` 的合法转移矩阵 |
| 3 | 打分只有 `-bm25×weight` | 7.2 给出三因子加权公式、分层优先级、归一化方式 |
| 4 | 无并发控制说明 | 6.5.2 乐观锁、`BEGIN IMMEDIATE`、`UNIQUE` 兜底 |
| 5 | 无迁移方案 | 15 章给出 9 步流程、关键 SQL、顺序约束、回滚 |
| 6 | 无验收标准 | 16 章给出 18 条测试、7 项指标、验收清单 |
| 7 | 无容量估算 | 8.5 给出 10 万条规模的行/索引/FTS/冷存估算 |
| 8 | 无错误码 | 9.2 给出 13 个错误码与客户端应对 |
| 9 | 无备份恢复 | 13.5 给出 `.backup` 策略与季度演练 |
| 10 | 无后台任务互斥 | 4.2 用 `flock` 保证 `maintenance`/`media_worker` 不重叠 |

### B.5 纠正的口径问题

| # | 位置 | 原表述 | 问题 | 本方案 |
|---|---|---|---|---|
| 1 | S1 二章架构图 | “6 个触发器 + 4 个索引” | 与 5.4 节 “6 张表 + 9 个触发器 + 4 个索引” 矛盾 | 统一为 **6 个触发器、18 个索引**，并列出明细（5.16） |
| 2 | S1 五章 decay | “task ×0.95 下限 0.1”；九章 “~20 天 weight=0.1” | `0.95^20≈0.358`，算术不成立；到 0.1 需 ≈45 天 | 改为 **≈45 天**，并把天数由配置推导；若需 20 天应设 `0.89`（6.11.1） |
| 3 | S1 二章 | “FTS5 BM25 + 时间混合衰减检索” | 五章公式 `score=-bm25*weight` 无时间因子，前后不符 | 7.2 补 `S_rec` 时间因子并给出权重 |
| 4 | S1 十二章 | `jieba` 标注“中文分词(预留)” | 实际 FTS 用 `unicode61`，中文检索形同虚设（整句被当一个 token） | jieba 改为实依赖并预分词写入（5.12） |
| 5 | S1 六章 | `POST /api/resolve` body 为 `{entry_id, action: keep` | 语句截断，接口定义不完整 | 9.4 补全为 `conflict_id + resolution` 四值枚举 |
| 6 | S1 三章 | `entry_id TEXT PK` | FTS5 只能按 rowid 删除；TEXT 主键表的 rowid 在 VACUUM 后可能变化，导致索引错位 | 增设 `row_id INTEGER PK AUTOINCREMENT`，`entry_id` 为 UNIQUE |
| 7 | S1 六章 | `GET /api/pin?id=` 切换置顶 | GET 带副作用，会被预取/缓存重复触发 | 改为 `POST /api/pin`（9.4） |
| 8 | S1 六章 | 看板以 `file://` 双击打开发起 fetch | 与“加 token + CORS”叠加会落到 `Origin: null`，等于对任意本地文件开放 | 同源托管看板（9.5） |
| 9 | S1 七章 | “7 个面板” | 无冲突页/音频页/冷归档页的定义，S2 要求新增 | 扩展为 9 个页面并标注依赖接口（11.1） |
| 10 | S1 八章 | `cp memory.db` 式备份（隐含） | WAL 模式下直接复制会丢失 `-wal` 中的已提交事务 | 强制使用 `.backup`（13.5） |
| 11 | S1 十章 | “WAL 多读单写 + ThreadingMixIn” | 未说明连接与线程的关系，易写成跨线程复用连接 | 4.2 + 6.4 明确“一连接一线程 + `BEGIN IMMEDIATE`” |
| 12 | S2 六章 | “L0 处理从 `SET l0_raw_content=NULL` 改为 `archive_l0()`” | 未说明“何时”归档，隐含“先热后冷”，需要多一列 `l0_hot` 与一次迁移 | 改为**写入即落盘**（D4），省一列与一次迁移 |
| 13 | S2 六章 | “哈希去重：同哈希 L0/音频只存一份，多条目共享” | 无表承载“物理文件 ↔ 逻辑引用”关系，`ref_count` 无处安放 | 新增 `memory_blobs`（5.6） |
| 14 | S2 七章 | “冲突页展示 `pending_merge`” | 无表存冲突对象、判定依据与建议动作，页面无数据可渲染 | 新增 `memory_conflicts`（5.9） |
| 15 | S2 一章 | “tokenizer 改 jieba 分词写入，或 trigram” | 二者机制不同（预分词 vs 三字滑窗），二选一未定 | 定 jieba 为主方案；trigram 不再考虑——语义召回已由向量承担（5.18） |
| 16 | S2 十一章 | supersede 与 `archive_manager` 分列 P0/P1 | 版本字段与事务必须一次落库；`doc_id` 外键要求写入路径一开始就走 `put_document` | 两项前移 P0（17.4） |

## 附录 C 项目结构

```
tinderbox/
├── .env / .env.example / .gitignore
├── requirements.txt
├── README.md                          # 快速开始 + 配置说明
├── dashboard.py                       # HTTP 入口（薄）
├── mcp_server.py                      # MCP 入口（薄）
├── dashboard_v2.html                  # 单文件看板
├── schema.sql                         # 全部 DDL（供 db.py executescript）
├── triggers.sql                       # 6 个触发器
├── src/
│   ├── __init__.py
│   ├── config.py                      # 设置
│   ├── db.py                          # 连接 / init / 自检
│   ├── textproc.py                    # 归一化 + jieba + MATCH
│   ├── llm.py                         # DeepSeek 客户端（重试/清洗/降级）
│   ├── storage.py                     # 写入 / 取代 / 状态操作
│   ├── ingest.py                      # 分块 / 提炼 / 去重 / 落库
│   ├── retriever.py                   # 三模式检索 + 打分
│   ├── version_chain.py               # 版本组与链
│   ├── conflict_guard.py              # 冲突判定
│   ├── archive_manager.py             # 冷归档 / TTL / 恢复 / 对账
│   ├── decay.py                       # 衰减与每日管道
│   ├── asr_adapter.py                 # ASR 协议 + 两实现
│   ├── media_ingest.py                # 媒体入库
│   ├── exporter.py                    # Obsidian + Git 异步
│   ├── maintenance.py                 # CLI 入口
│   └── migrations/
│       ├── __init__.py
│       └── v2_0_0.py
├── archive/                           # 冷存储（不入 Git）
├── vault/                             # Obsidian 仓库（独立 Git）
├── cache/restore/                     # 临时解压
├── var/                               # 锁、队列、日志、词典
└── tests/
    ├── conftest.py                    # 临时库 fixture
    ├── test_textproc.py               # T1, T2
    ├── test_storage.py                # T10, T11
    ├── test_supersede_concurrency.py  # T5, T17
    ├── test_retriever.py              # T3, T4, T7
    ├── test_conflict_guard.py         # T6
    ├── test_archive_ttl.py            # T8
    ├── test_media_e2e.py              # T9
    ├── test_migration.py              # T12
    ├── test_perf.py                   # T13, T14
    ├── test_failure.py                # T15, T16
    ├── test_api_security.py           # T18
    └── fixtures/
        ├── recall_queries.json        # 200 条召回评估集
        └── conflict_pairs.jsonl       # 100 对标注样本
```

---

*本方案基于 S1《Memory_Vault_Architecture.md》与 S2《一.docx》合并而成。凡与原文不一致处，均已在附录 B.5 列明理由。实施过程中若发现新的口径冲突，应以「数据不丢、动作可逆、行为可配置」三原则裁决，并回写本文档。*

## 附录 D v2.1 相对 v2.0 的变更对比

本节只列**影响实现或数据**的改动，纯文字润色不列。v2.0 原文存于 `history/`，可逐字对照。

### D.1 结构性变更

| # | 位置 | v2.0 | v2.1 | 为什么改 | 影响面 |
|---|---|---|---|---|---|
| 1 | 5.7 | `memory_l0_archive`：主键 `entry_id`，`blob_hash` 带 `UNIQUE` | `memory_documents`：主键 `doc_id`，一份材料一个文件 | 原设计“每条 L1 存一份归档记录”与“多条目共享原文”冲突，第 2 条 L1 就撞唯一约束 | 表结构、迁移、6.10、API |
| 2 | 5.4 | `l0_ref` / `l0_hash` / `l0_size` | `doc_id` + `l0_offset` / `l0_length` + `chunk_index` | 引用从“文件”降为“区间”，一份材料可被 N 条共享 | DDL、索引、审计 |
| 3 | 3.4 / 5.4 | `l0_state`：`none/cold/restoring/purged` | `none/live/purged` | 状态收敛到材料表，条目只留快照 | 状态机、API |
| 4 | 5.8 | `memory_media.transcript_blob` | `transcript_doc_id` | 转写全文本身就是一份材料，应进 `memory_documents` | DDL |
| 5 | 5.13 | `idx_l0_expires`（16 个索引） | `idx_docs_expires` + `idx_docs_live_ref` + `idx_entries_doc`（18 个） | 回收判断改为按材料 | 索引清单 |

### D.2 行为变更

| # | 位置 | v2.0 | v2.1 | 为什么改 |
|---|---|---|---|---|
| 6 | 6.6 | 固定 2500 字步长 + 200 字重叠 | 800 / 2500 / 6000 区间，按标题→空行→句末→硬切 | 固定步长会把一件事劈成两半 |
| 7 | 6.6 | 重叠文本当正文送进模型 | 滚动上下文：前序 L1 只读传入 | 重叠会被重复提炼，且救不了跨 2000 字的延续 |
| 8 | 6.6 | 逐块直出，无全局视角 | 新增 `topic` / `continues_previous` + 文档级 reduce 归并 | A→B→A 回环无法缝回同一版本组 |
| 9 | 6.10.2 | `restore_l0` 写临时文件、返回路径 | `restore_span` 返回区间文本 + 前后各 500 字 | 片段只有几百字，不必落盘；补上下文才看得懂 |
| 10 | 6.10.3 | 仅 TTL 清理 | 四条触发 + 瘦身 + 磁盘水位 | 整篇存会空间放大，需要更细的回收 |
| 11 | 8.3 | “用过就续期”（restore 顺延 TTL） | 恢复不延长 TTL，续期只靠 `pin` | 只读一次的材料会被永久占位 |
| 12 | 8.3 | 归档条目永久保留 | 3 年后导出为文件、从库里裁掉 | 归档表与主库同文件，会无限增长 |
| 13 | 16.1 | 18 条用例 | 21 条（新增 T19 跨块延续 / T20 回收瘦身 / T21 长文唯一性） | 覆盖新机制 |

### D.3 不变的部分

- 技术选型（SQLite + FTS5 + DeepSeek + MCP + Obsidian）不变；
- 双 FTS（active / history）+ 6 个触发器不变；
- 版本链、冲突治理、衰减数学口径不变；
- API 路径与 MCP 工具清单不变，仅 `/api/l0/restore` 的返回体由“路径”改为“文本 + 区间”。

### D.4 修订记录约定

自 v2.1 起，每轮修订都在本附录追加一节 `D.n`，并在仓库根 `变更日志.md` 留一份同样的对照表。正文只呈现改后的方案，修订痕迹集中放在附录与变更日志，避免方案本身被历史版本稀释。

### D.5 v2.2 相对 v2.1 的变更

| # | 位置 | v2.1 | v2.2 | 为什么改 |
|---|---|---|---|---|
| 1 | 5.18（新） | 无向量表 | `memory_vectors`（vec0，`int8[512]`），只存活跃条目 | 字面匹配已到天花板 |
| 2 | 6.1 | 模块表无向量能力 | +`embedding.py`（双后端：本地 ONNX / 云端 API） | 向量化与 KNN 独立成模块 |
| 3 | 6.9.3 | FTS 单路召回，BM25 归一化当相似度 | 向量为主 + FTS 兜底，统一用 cosine | “换了说法”的冲突判不出来 |
| 4 | 7.2 | `S_rel` = BM25 查询内归一化 | `S_fuse` = RRF(FTS 排名, 向量排名)，k=60 | BM25 与 cosine 量纲不可比，归一化参数会随语料漂移 |
| 5 | 8.5 | 主库 ≈ 225 MB | ≈ 240 MB（+15 MB 向量，只算活跃条目） | 容量口径更新 |
| 6 | 2.3 / 16.1 | Recall@10 ≥ 0.85；21 条用例 | ≥ 0.90；23 条（+T22 混合召回 / T23 降级） | 指标随能力上调 |
| 7 | 17.1 / 17.4 | P1 8 天，向量在 P4 | P1 11 天，向量进 P1；P4 减 1 天；总工期 31 → 34 人日 | 能力前移，且理由写进优先级表 |
| 8 | 18 | 12 条风险 | 14 条（+R13 模型换代 / R14 性能） | 新组件带来新风险 |
| 9 | 19 | D6 待定 | D6 已定，新增 D7（嵌入模型选型） | 决策收敛，不留悬空 |

**一条不可让步的红线**：任何一环不可用（模型缺失、扩展缺失、维度不符）都必须退化为纯 FTS，而不是报错。检索是记忆库的命脉，不能因为一个可选加速器就整体不可用——这条写进了 4.4 与 6.9.3，由 T23 守着。

### D.6 v2.3 相对 v2.2 的变更

只有一个决策：嵌入模型从 `bge-small-zh-v1.5`（512 维）换成 `bge-m3`（1024 维）。它牵动四个数字。

| # | 位置 | v2.2 | v2.3 | 为什么 |
|---|---|---|---|---|
| 1 | 5.18 / 6.2 | `int8[512]`，`EMBED_DIM=512` | `int8[1024]`，`EMBED_DIM=1024` | 换模型即换维度，必须重建向量 |
| 2 | 8.5 | 向量 ≈15 MB，主库 ≈240 MB | 向量 ≈30 MB，主库 ≈255 MB | 1024 维 int8 每条 1 KB |
| 3 | 2.3 G4 / 16.1 T13 | 混合检索 p95 ≤150 ms | 混合 ≤300 ms（缓存命中 ≤120 ms），纯 FTS 降级仍 ≤150 ms | bge-m3 查询编码 80～150 ms，是 FTS 的 10 倍；指标不能装作没变 |
| 4 | 13.2 / 18 | `fastembed`，无内存条目 | `onnxruntime`+`transformers`，新增 R15 内存争用 | 模型 0.6 GB 磁盘、1.2 GB 常驻，与 faster-whisper 抢内存 |

**这轮改动的性质不同**：前两轮是“修结构”，这一轮是“拿延迟换质量”。bge-m3 的中文长句与同义改写召回明显更好，代价是每次查询多 100 ms 左右。如果后续实测发现交互体感变差，回退路径很清晰——把 `EMBED_MODEL` 与 `EMBED_DIM` 改回 small 档并重建向量，其余代码不动。

### D.7 v2.4 / v2.5 的收口改动

v2.4 是一次全篇一致性审计，v2.5 是砍范围。两者都不动结构，只把文档里互相打架的地方对齐。

| # | 位置 | 旧 | 新 | 为什么 |
|---|---|---|---|---|
| 1 | 7.8 | 10 万条 p95 < 150 ms | 混合 300 / 缓存命中 120 / 纯 FTS 150 | 与 2.3 G4 矛盾 |
| 2 | 9.4 | `/api/l0/restore` 返回临时路径 | 返回 `{text, offset, length, context}` | 与 6.10.2 实现矛盾 |
| 3 | 12.2 | `l0_state: cold` | `l0_state: live` | 状态枚举早已变更 |
| 4 | 5.13 / 5.16 / 8.5 | 索引数 15 / 17 / 18 混用 | 统一 18（主库 17 + 归档 1） | 归档表索引一直没计入 |
| 5 | 6.9.1 | “若启用向量（P4）” | 向量路常态启用 | v2.2 起已是 P1 |
| 6 | 5.12 | “P4 可选优化” | “后续可选优化（未排期）” | 该项不属于 P4 范围 |
| 7 | 2.4 / 17.1 | 非目标写“不做加密存储（P4 可选）”，P4 却列了“加密导出” | 非目标写死：存储与导出都不做加密；P4 移除该项，工期 34 → 33 人日 | 范围自相矛盾；加密导出会引入密钥管理，是产品里最容易做错、也最容易给人虚假安全感的东西 |

**关于砍掉加密导出**：这不是省事，是避坑。真正的加密导出等于要自己做密钥派生、轮换、丢失恢复——任何一环做错，用户以为安全而实际不安全。磁盘加密有 BitLocker / VeraCrypt，文件加密有 7z，都比自研可靠。产品说不做，比做了半套更诚实。

### D.8 v2.6 相对 v2.5 的变更

| # | 位置 | v2.5 | v2.6 | 为什么 |
|---|---|---|---|---|
| 1 | 5.4 | 无验证标记 | `verified_at` / `verified_by` / `verified_reason` 三列 | 分档判据需要一个可记录的字段 |
| 2 | 6.10.2 | `doc_ttl_days` 单一档期 | 落下时按未验证长档，验证后提前释放 | TTL 在写入时定死，但验证发生在之后 |
| 3 | 6.10.3 | 一条 TTL 判定 | 两条：未验证档到期 / 全部已核对且满 180 天 | 回收口径从“日历”变为“内容” |
| 4 | 8.3 | 单档 365 天 | 未验证 730 / 已验证 180 | 原文的价值取决于摘要是否可信，不取决于新旧 |
| 5 | 9.4 / 6.5.3 | 无标记入口 | `POST /api/verify` + `mark_verified()` | 需要一个人能按下“这条我认了”的按钮 |
| 6 | 16.1 | 23 条用例 | 24 条（+T24 分档保留） | 新策略必须有验收口径 |

**核心那句话**：该优先释放的不是旧的，是**已被核对过的**。越确信的记忆越不需要原文，越不确定的越不能删原文。

### D.9 v2.7 相对 v2.6 的变更

v2.6 把 `pinned` 当成“已核对”的来源之一，这是错的。置顶表达的是**用户想怎么组织**，核对表达的是**内容可不可信**——两者混用，分档策略就退化成“用户没置顶的都留 730 天”。

| # | 位置 | v2.6 | v2.7 | 为什么 |
|---|---|---|---|---|
| 1 | 5.4 | `verified_reason ∈ edited/pinned/adjudicated/imported` | `authored/adjudicated/reviewed` | 去掉 `pinned`；`edited`/`imported` 语义含糊，合并为 `reviewed`/`authored` |
| 2 | 6.5.3 | `set_pin` 只影响权重与排序 | 明确标注“不写 `verified_at`” | 防止实现者顺手打标 |
| 3 | 8.3 | 只说“已验证 180 天” | 新增「三种别删」对照表 + 三种验证来源 | 读者必须能一眼分清 pin/anchor/verified |
| 4 | 9.4 | `/api/verify` 的 reason 含 `pinned` | 去掉，只留三种人工来源 | 置顶不再触发验证 |
| 5 | 11.x | 徽标混排 | 组织标记（图钉/锚）与质量徽标（已核对）分开显示 | UI 混着放，等于每天在误导用户 |
| 6 | 16.1 | 23 → 24 条 | 24 → 25 条（+T25 置顶不得写验证位） | 防止这条规则被后人改回去 |

**一句话**：`pin` 回答“我想先看哪条”，`anchor` 回答“哪条不该淡忘”，`verified_at` 回答“哪条我确认过”。三个问题，三个字段，不互相推导。

### D.10 v2.8：更名为 Tinderbox

产品定名 **Tinderbox**，全案同步。改名本身不改任何行为，只改标识——但标识散落在七种位置，漏一处就会让后来者困惑。

| # | 位置 | 旧 | 新 |
|---|---|---|---|
| 1 | 文档标题、页眉、页脚 | Memory Vault 记忆库完整方案 | **Tinderbox 记忆库完整方案** |
| 2 | 项目目录 | `memory_vault/` | `tinderbox/` |
| 3 | 部署路径 | `/opt/memory_vault`、`/var/log/memory_vault`、`/backup/memory_vault` | `/opt/tinderbox` 等 |
| 4 | systemd 单元 | `memory-vault.service`、`memory-vault-maintenance.timer` | `tinderbox.service`、`tinderbox-maintenance.timer` |
| 5 | MCP 服务名 | `"memory-vault"` | `"tinderbox"` |
| 6 | HTTP 服务标识 | `server_version = "MemoryVault/2.0"` | `"Tinderbox/2.8"` |
| 7 | 交付文件名 | `记忆库完整方案_v2.7.docx` | `Tinderbox_记忆库完整方案_v2.8.docx` |

**刻意不改的两处**：

- **数据库文件名仍是 `memory.db`**。它描述的是“记忆库”这个领域对象，不是产品名；改名会让所有运维脚本、备份命令、迁移文档一起失效，收益为零。
- **表名前缀仍是 `memory_`**（`memory_entries`、`memory_documents`…）。理由同上：它们是领域名词，不是品牌。

规则：**品牌名随产品变，领域名随语义变**。两者混用，才会出现“改了名之后半年不知道哪个是产品、哪个是表”的局面。

### D.11 v2.9：命名释义的更正

v2.8 把 Tinderbox 解释成“装火种的盒子”，读者会理解成“保存/收藏”，方向正好反了。

| 位置 | v2.8 | v2.9 |
|---|---|---|
| 2.1 命名注解 | “一个小盒子，存着火种……安静地存着，要用时能燃” | “安徒生《打火匣》：擦一下火石，狗把你想要的东西叼回来” |

差别不在修辞，在**产品隐喻**：

- “存着火种”强调的是**保存**——那是档案盒、保险箱的意象；
- “擦一下，东西被叼回来”强调的是**召唤**——一次检索、一次提问，记忆应声而至。

这个产品真正的价值不在“存得住”（谁都能存），而在“**问得着**”。命名释义写错，会把注意力引向错误的方向。

### D.12 v2.10：L1 从“结论”改为“结论 + 依据”

原契约写着“只提炼可复用的结论，不复述过程”。这句话被 demo 证伪了：**只留结论的记忆，三个月后无法复用，因为你不知道该不该信它**。

| 位置 | v2.9 | v2.10 | 为什么 |
|---|---|---|---|
| 6.6.5 提示词要求 | “只提炼可复用的结论，不复述过程” | “写成『做了什么决定——因为什么』” | “不复述过程”被误读成“只留结论”，把依据一起丢了 |
| 5.4 字段说明 | `l1_summary` = 摘要 | `l1_summary` = **结论 + 依据**，不是截断的原文 | 截断式摘要是最常见也最隐蔽的质量事故 |
| 6.6.3 契约 | 只有字段表 | 新增“什么样的 L1 算合格”三级对照 | 不给判据，实现者就会用 `[:120]` 交差 |

**判据一句话**：依据里只保留**能改变判断的那部分**（价格差、断货次数、管理成本），其余细节留在 L0。摘要不是原文的缩水版，是原文的**可执行版**。

### D.13 v2.11：链首必须带前因

v2.10 解决了“一条记忆凭什么成立”（依据），这一轮解决“这件事为什么会发生”（前因）。两者是一对：

| | 方向 | 回答 | 字段 |
|---|---|---|---|
| 依据 | 横向 | 为什么**这样**定 | `l1_summary` 的后半句 |
| 前因 | 纵向 | 为什么**会有这件事** | `context`（仅链首） |

| 位置 | v2.10 | v2.11 | 为什么 |
|---|---|---|---|
| 5.4 | 无 `context` 字段 | 新增，仅 `version_no = 1` 填充 | 链首没有上一版，必须自己交代全貌 |
| 6.6.3 契约 | 输出 `topic` / `continues_previous` / `topic_shift` | 增加 `context`，且只允许首条输出 | 模型默认会每条都写背景，必须显式约束 |
| 6.6.6（新增） | — | “前提 / 计划 / 发现 / 结果”四段对照表 + 实践坑 | 抽象要求落不下地，要给出可对照的样板 |

**为什么只给链首**：后续版本若都重复背景，链会变成复读机；靠 `predecessor_id` 回溯既精确又省空间。

**一个实测教训**：按“信息密度”排序会系统性丢掉铺垫。缘起、候选、约束这些段落信息量低，但缺了它们结论就是孤证。所以提炼排序只能用来**决定留几条**，不能用来**决定前因**——前因必须按原文位置往前取。

### D.14 v2.12：概念层（星网）与阈值实测

版本组管“同一件事的第几版”，概念层管“哪几件事属于同一个项目”。缺了后者，“讲讲咖啡车项目”这种问法无法回答。

| 位置 | v2.11 | v2.12 | 为什么 |
|---|---|---|---|
| 5.19（新增） | 无 | `memory_concepts` + `memory_entry_concepts`，多对多 + 层级 + `is_seed` | 一个事实本就属于多个上下文 |
| 6.15（新增） | 无 | 挂靠流程、margin 闸门、待归类、概念提议 | 机器只能挂靠，不能建网 |
| 附录 A | — | `CONCEPT_MARGIN` / `CONCEPT_TOPK` | 阈值必须可标定 |
| 16.1 | 25 条用例 | +T26 概念挂靠精度 | 不给指标，实现者会拍脑袋定 0.78 |

**一次真实标定**（25 条 / 9 概念，bigram 替身）：accuracy@1 只有 52%；命中与错配的余弦分布大幅重叠，绝对阈值分不开；改用 margin 后，最高 10% 的那批准确率 100%，但要覆盖全部只有 52%。

**由此推翻了一个拍脑袋的数**：上一版草稿里“0.8 以上算同一概念”是凭空的。阈值不是常数，它随表示变化——换模型就得重新标定。

**原则沿用**：低置信度不自动挂，进「待归类」；新概念只提不建，等人命名。和冲突治理一样：高危动作不自动执行。

### D.15 v2.13：互补关系与闸门不对称

之前只有三种处置：取代、挂起、归档。缺了最常见的第四种——**补充**：新信息加进来，旧记忆一个字不改。

| 位置 | v2.12 | v2.13 | 为什么 |
|---|---|---|---|
| 5.20（新增） | 无 | `memory_relations`：complement / related / derived_from | 互补不改变任何一方，不该占 status |
| 6.9.4（新增） | 未定义 | 三种关系的闸门对照表 | 判错代价差三个量级，闸门不能一样严 |
| 16.1 | 26 条用例 | +T27 补充记忆不触碰原有记录 | 这是最容易被“顺手合并”搞坏的地方 |

**一次真实验证**（30 条既有 + 5 条补充）：原有条目快照前后完全一致（0 条改动）、冲突数不变、识别出 3 组互补关系、新词可检索。

**闸门设计的原则**：`override` 判错不可逆，所以严；`complement` 判错只是推荐不准，所以松。**同一个模型，不同的信任级别**——这条以前没写清楚。

### D.16 v2.14：视图层的两条约定

v2.13 之前，文档只写了 API 的模式参数，没写界面该怎么组织。实现时的两个决定值得固化：

| 位置 | 旧 | 新 | 为什么 |
|---|---|---|---|
| 11.1 页面表 | 9 个页面，搜索页带「现在/历史」开关 | 11 个页面，新增「演变」「星网」，搜索改为一次给全 | 模式切换是认知负担，不是功能 |
| 11.2 交互 | 只有状态徽标与事件委托 | 补「视图分工」「星网三层折叠」「间隔天数即信号」 | 不给约定，实现者会把星网做成一条长列表 |
| 7.1 | 三模式平铺 | 加注：界面只暴露「全部 / 演变」 | 澄清 `mode` 是能力不是必答项 |

**两条可复用的原则**：

1. **该由系统判断的，别推给用户。** “这条记忆还有效吗”是系统知道的，界面却要用户先选模式——把判断成本转嫁了。
2. **折叠优先于滚动。** 项目 → 分组 → 条目三层，默认只展开到看得清结构的那一层；长列表是失败的默认值。

**实测细节**：版本链上标 `+N 天` 不是装饰——一条改过四次的决策，间隔从 31 天拉到 92 天，说明它在收敛；反过来就是在失控。

### D.17 v2.15：配对优先于判定

v2.13/6.9.4 解决了“闸门该多严”，这一轮解决更前置的问题：**跟谁比**。

| 位置 | v2.14 | v2.15 | 为什么 |
|---|---|---|---|
| 6.9.5（新增） | 只按相似度挑前任 | 先分言语行为，再比相似度 | 罗列段字面重合最高，却永远不该被取代 |
| 配对规则 | 全量候选 | 候选前任限定为 change / decision | 不下结论的话没有“被取代”这回事 |

**三次踩坑的同一个病**：判断依据选错了维度——按字面重合（该按语义）、按 row_id（该按原文位置）、按自身条数（该按子树总数）。

**代价**：这条规则依赖分类准确。分类错了配对照样错，只是错得少。真正的解法还是向量召回，分类只负责把明显不该配的排掉。

### D.18 v2.16：把范围收窄

写了两天、做了两天 demo 之后回头看，方案里有大块内容是“设想要是有人天天用”的产物，而不是“现在就需要”。

| 项 | v2.15 | v2.16 | 为什么 |
|---|---|---|---|
| P4（多用户 + 向量压缩） | 3 天 | **删** | 单用户谈隔离没意义；30 MB 向量做量化压缩收益约等于零 |
| 看板 | 11 个页面 | **5 个**（搜索 / 演变 / 星网 / 冲突 / 详情） | demo 证明 3 个入口就够用，其余 6 个不阻塞任何链路 |
| 向量检索进 P1 | 是 | 否 | 30 条真实记忆上实测：LSA 概念挂靠 50% vs bigram 50%，配对更差——没证明自己 |
| 音频 / Obsidian / 迁移 | 主线（7+2+2 天） | **非必要** | 保留能力描述，但不占主计划 |
| 核心工期 | 33 人日 | **21 人日** | 砍掉 12 天 |

**判断依据是一条**：demo 里真跑通过的算核心，只有文字描述的算可选。按这条尺子，原来的 33 人日里有一半是没被任何一行代码验证过的设想。

**没砍但降级的**：概念层的自动挂靠（accuracy 50%，只能人工搭骨架）、部署的 systemd/监控（改成“能跑 + 能备份”）。

> **v2.16 附注**：上面这张表里“向量检索 → 非必要”的改判，是本轮唯一一处**推翻自己此前结论**的地方——v2.2 曾以“配对卡在字面不重合”为由把它从前 P4 提到前 P1。实测数据不支持这个判断，所以撤回。

### D.19 v2.17：把 demo 实测写进文档

这一轮没有新设计，全是**把两天的实测结果钉进正文**——因为方案里关于 LLM 的段落此前只有设想。

| 位置 | 新增 | 依据 |
|---|---|---|
| 6.6.4 | 规则 vs LLM 的量化对比表（依据率 14% → 94%） | sample.txt 实跑 |
| 6.6.4 | 两种产物对照 + 对检索的连带影响 | 查「选址」的 top1 变化 |
| 6.6.7 | LLM 调用可重放（record/replay） | 三次运行冲突数 1/0/0 |
| 6.9.6 | 两个判定器取并集 | 规则 3 处 vs LLM 1 处 |
| 16.1 | +T28 LLM 提炼可复现 | 122 行日志逐行一致 |

**这轮最值得记的一条**：LLM 的不确定性不是准确率问题，是**可测性问题**。

同一份输入连跑三次，冲突数 1/0/0、链条 4/3/2——所有“跑一遍看着对”的验证方式全部失效。加了缓存之后，21.5 秒降到 0.25 秒只是副产品，真正的收益是**回归重新变得可比**。

**顺带修掉的四个 bug**（都是“LLM 换了措辞，规则层跟不上”）：

| 现象 | 病因 |
|---|---|
| 四版链缩成两版 | `定用`/`最终定`/`改到`/`改换` 不在穷举词表里 |
| 冲突突然消失 | 词表换正则时漏了「为」，`定为` 被判成 note |
| 判定器打架 | 规则激进、LLM 保守，取交集会漏判 |
| 每次结果不同 | 没有重放机制 |

前两个纯粹是手误，**而且都只能靠跑一遍看输出发现**——这正是 6.6.7 存在的理由。

### D.20 v2.18：人工裁决与实现进度

| 位置 | 新增 | 为什么 |
|---|---|---|
| 11.3 | 人工裁决的交互约定（五项）+ 真实展示样例 + 两个接口 | 这是唯一“必须有人在场”的页面，约定不写清就会做成一个默认回车就提交的危险按钮 |
| 17.5 | 实现进度表（跑通的打 ✅，没跑通的打 ❌） | 文档最容易自欺的地方：把“设计了”当成“做到了” |

**裁决页最关键的一条**：判定理由里保留**另一判定器的意见**。

并集机制（6.9.6）会让“规则说补充、模型说覆盖”这种分歧也挂起。挂起之后若不把分歧写给人看，人只会看到一个 0.95 的置信度，以为很确定——实际是两个判定器在打架。**把不确定性显式交出去，比给一个漂亮的置信度更诚实。**

**进度表的用法**：任何一次版本修订后重跑一遍 demo，能跑通的才准打 ✅。这张表胜过任何“完成度百分比”。

### D.21 v2.19：两个被真实长文本暴露的缺口

用鲁迅《呐喊》四篇（13,983 字，公有领域）做压力测试，冒出来两个与语料无关的真缺陷。

| # | 问题 | 性质 |
|---|---|---|
| 1 | `hard_max` 参数声明了却从未使用，分块只按空行切 | 实现 bug：参数没生效 |
| 2 | FTS 不做简繁归一，「長衫」与「长衫」永不相遇 | 设计缺口：全文没提过这件事 |

**为什么之前测不出来**：demo 的样例材料都有空行、都是简体。**只有换一种真实文本，才会同时踩到这两个坑。**

| 修复 | 实测 |
|---|---|
| 分块三级回退（空行 → 单行 → 句末 → 硬切）+ 上限断言 | 《故鄉》1 块 → 6 块；语料 4 块 → 18 块 |
| 498 对高频繁简字，在分词入口统一转简体 | 查「长衫」0 条 → 2 条；覆盖率约 15% |

**这两条比“小说档提示词”重要得多**：提示词只影响某一类语料，而分块和简繁归一影响**所有**材料——尤其“没有空行的文本”，那是粘贴内容的标准形态。

### D.22 v2.20：规则提炼的降级策略

| 位置 | 新增 | 依据 |
|---|---|---|
| 6.6.8 | 精确优先的三层策略（阈值 / 预算 / 兜底）+ 分数分布表 | 小说语料 175 条 vs 业务材料 22 条 |
| 6.6.8 | 两个实现陷阱（预算当筛选器、空链未判空） | 都实际崩过 |

**一句话**：降级路径的正确目标不是“多记”，而是“少而准”。LLM 不在的时候，系统的正确姿态是**保守**，不是勤奋。
