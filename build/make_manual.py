"""按小节块抽取，逻辑简单可核对。"""
import re
from pathlib import Path

BASE = Path(r"E:\记忆库")
# 自动取最新一版参考卷：手写版本号是"两份文档不同步"的根源
_CANDS = sorted(BASE.glob("Tinderbox_记忆库完整方案_v*.md"),
                key=lambda f: [int(x) for x in re.findall(r"v(\d+)\.(\d+)", f.name)[0]])
SRC = _CANDS[-1]
print(f"参考卷：{SRC.name}")
DST = BASE / "Tinderbox_实施手册_v1.0.md"
lines = SRC.read_text(encoding="utf-8").split("\n")

# 需要的：整章 or 具体小节
WHOLE_CH = {"9", "附录 A"}
SECTIONS = {"2.1", "2.2", "2.3", "3.1", "3.2", "3.3", "4.1", "4.2",
            "6.1", "6.6", "6.9", "7.1", "7.2", "8.1", "8.2", "8.3",
            "11.1", "11.2", "16.1", "17.1", "17.5"}

# 切成块：(层级, 编号, 标题, 正文)
blocks = []
cur = {"level": 0, "no": None, "title": "", "body": []}
for ln in lines:
    m = re.match(r"^(#{2,3})\s+(?:(\d+(?:\.\d+)*|附录\s+[A-Z]))?\s*(.*)$", ln)
    if m and len(m.group(1)) <= 3:
        blocks.append(cur)
        cur = {"level": len(m.group(1)), "no": (m.group(2) or "").strip(),
               "title": m.group(3).strip(), "body": [ln]}
    else:
        cur["body"].append(ln)
blocks.append(cur)

def emit_chapter(no: str, title: str):
    if no and no not in emitted:
        emitted.add(no)
        out.append(f"## {no} {title}".rstrip())


out, kept, emitted, cur_ch = [], [], set(), ("", "")
for b in blocks:
    if not b["body"]:
        continue
    no = b["no"]
    if b["level"] == 2:
        cur_ch = (no, b["title"])
        if no in WHOLE_CH:
            emit_chapter(no, b["title"])
            out.append("\n".join(b["body"][1:]).rstrip())
            kept.append(no)
        continue
    keep = no in SECTIONS or cur_ch[0] in WHOLE_CH
    if not keep:
        continue
    if cur_ch[0] not in WHOLE_CH:          # 只留小节时，补一个章标题
        emit_chapter(cur_ch[0], cur_ch[1])
    kept.append(no)
    out.append("\n".join(b["body"]).rstrip())

body = re.sub(r"\n{3,}", "\n\n", "\n\n".join(out))

# 第 5 章只要 DDL
ch5 = [i for i, l in enumerate(lines) if re.match(r"^## 5 ", l)][0]
ch6 = [i for i, l in enumerate(lines) if re.match(r"^## 6 ", l)][0]
ddl, fence = [], False
for ln in lines[ch5:ch6]:
    if ln.strip().startswith("```"):
        fence = not fence
        ddl.append(ln)
        continue
    if fence or ln.startswith("### 5."):
        ddl.append(ln)

ONE = """# Tinderbox 实施手册

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

"""

DOC = ONE + re.sub(r"\n{3,}", "\n\n", "\n".join(ddl)) + "\n\n---\n\n" + body + "\n"
DST.write_text(DOC, encoding="utf-8")
print(f"手册 {len(DOC):,} 字符（约 {len(DOC) / 1500:.0f} 页），占参考卷 {len(DOC) / len(''.join(lines)):.0%}")
print("保留：", " / ".join(kept[:30]))
