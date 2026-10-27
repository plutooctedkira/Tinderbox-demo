# build/ —— 文档的构建与校验

这里不是产品代码，是**文档流水线**。产品在 `demo/`。

## 改完文档，固定跑这五步

```powershell
$py = "C:\Users\pelican\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

& $py build\fix_quotes.py 路径\某.md   # 0. 先把正文里的半角引号规范成中文引号
& $py build\make_manual.py       # 1. 从最新参考卷抽出手册（改了参考卷就跑）
& $py build\build_docx.py        # 2. 参考卷 md → docx
& $py build\build_manual.py      # 3. 手册 md → docx
& $py build\validate.py          # 4. 校验：表格/引号/章节/一致性
& $py build\validate_manual.py   #    手册也要校验一遍
```

**第 0 步不要省**：写正文时很容易混进半角 `"`。`validate` 会报行号，但**先修再生成**，
比"生成完发现 docx 里是半角引号"省一轮。这一步只动正文行，跳过代码块与行内代码。

**第 4 步的四类检查**：

| 检查 | 抓什么 |
|---|---|
| 表格列数 | 某行 `\|` 数量与表头不一致（渲染会错位） |
| 代码块 | 围栏是否配对；行宽 > 105 字符 |
| 引号 | 正文里的半角 `"`（应改中文引号） |
| **一致性** | **未排期功能混进 schema 或配置表**——硬性档违规即失败 |

## 三条规矩

1. **只改 `.md`，再生成 `.docx`**。直接改 docx 下次生成就被覆盖。
2. **版本号不要手写**。手册抽取脚本会自动找最新一版参考卷；`build_docx.py` 里的版本号改一处即可。
3. **砍掉的功能要标「预留 / 未启用」**。否则一致性检查会红——这正是它存在的意义。

## 脚本清单

**生成**

| 脚本 | 干什么 |
|---|---|
| `build_docx.py` | 参考卷 md → docx（封面、目录、章节、表格样式） |
| `make_manual.py` | 从参考卷抽取实施手册（自动跟随最新版本） |
| `build_manual.py` | 手册 md → docx |
| `make_figures.py` | 生成 3.1 分层图、4.1 架构图（PIL） |

**校验**

| 脚本 | 干什么 |
|---|---|
| `fix_quotes.py` | 半角引号 → 中文引号（跳过代码块；幂等，可反复跑） |
| `validate.py` | 参考卷的四类检查 |
| `validate_manual.py` | 手册的四类检查 |
| `determinism.py` | 同一输入跑两次，日志是否逐行一致（验 record/replay） |
| `regress.py` | 重构前后日志结构对比（忽略 ID/数字） |

**体检（一次性，留着有用）**

| 脚本 | 干什么 |
|---|---|
| `audit.py` | 重复文件、临时产物、各目录体积 |
| `cleanup.py` | 删缓存 + 历史版本打包（校验后再删原文件） |
| `weigh.py` | 各章字符数占比——判断文档胖在哪 |
| `review_doc.py` / `review_doc2.py` / `review_doc3.py` | 交叉引用、常量冲突、伪代码、编码噪点 |
| `lint_demo.py` | demo 的静态体检：长函数、死代码、循环里的 SQL |
| `verify16.py` | 抽查某一版的改动是否真的落进文档 |

## 目录外的东西

| 路径 | 是什么 |
|---|---|
| `../figures/` | 两张插图的 PNG（docx 引用它们，别删） |
| `../历史归档/` | 旧版本：v2.0（原名 Memory Vault）、v2.9–v2.14 压缩包、v2.15 起逐版 md/docx |
