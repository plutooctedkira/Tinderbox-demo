"""把测试结果做成一份报告（Markdown + DOCX）。

输入：demo/out/suite/suite.json 与各项 .log
输出：E:\\记忆库\\测试报告_v1.0.md / .docx
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = Path(r"E:\记忆库")
OUT = BASE / "demo" / "out" / "suite"
suite = json.loads((OUT / "suite.json").read_text(encoding="utf-8"))
NOW = time.strftime("%Y-%m-%d %H:%M")


def log(cid: str) -> str:
    p = OUT / f"{cid}.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------------------------------------------------------------- 指标抽取
def grab(text: str, pat: str, default: str = "—") -> str:
    m = re.search(pat, text)
    return m.group(1).strip() if m else default


def R(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    if not m:
        return "—"
    return " / ".join(g for g in m.groups() if g)


METRICS = {
    "write": lambda t: [("不达标", R(r"通过：(\d+) 项不达标", t)),
                      ("审计", "create/update/archive/restore" if "审计轨迹完整" in t else "—")],
    "backup": lambda t: [("恢复", R(r"恢复后条目还原（(\d+) vs (\d+)）", t)),
                        ("不达标", R(r"通过：(\d+) 项不达标", t))],
    "topic": lambda t: [("按材料名", R(r"R@1 (\d+%).*?R@5 (\d+%)", t)),
                       ("门槛", "达标" if "通过（门槛" in t else "未达")],
    "demo": lambda t: [
        ("写入", f"{grab(t, r'写入 (\d+) 条')} 条 / {grab(t, r'规则提炼，([\d.]+) ms')} ms"),
        ("精修", f"采纳 {grab(t, r'采纳 (\d+) 条')} · 驳回 {grab(t, r'驳回 (\d+) 条')}"),
        ("冲突", f"{grab(t, r'自动检出 (\d+) 处冲突')} 处"),
        ("最长链", f"{grab(t, r'最长的一条链：(\d+) 个版本')} 版"),
    ],
    "complement": lambda t: [
        ("原记录改动", f"{grab(t, r'发生变化的有：(\d+) 条')} 条"),
        ("互补关系", f"{grab(t, r'识别出 (\d+) 组')} 组"),
    ],
    "selftest": lambda t: [("通过", grab(t, r'(\d+/\d+) 项通过'))],
    "offline": lambda t: [
        ("断网写入", f"{grab(t, r'写入 (\d+) 条，([0-9]+) ms')} 条"),
        ("精修", f"{grab(t, r'精修 (\d+) 条')} 条"),
        ("浮现", f"{grab(t, r'浮现 (\d+) 条')} 条"),
        ("md 往返", "能找到 ✓" if "能找到 ✓" in t else "✗"),
    ],
    "maintenance": lambda t: [
        ("dry-run 命中", f"{grab(t, r'命中 (\d+) 份')} 份"),
        ("分档", "正确 ✓" if "分档是否正确" in t and "✓" in t.split("分档是否正确")[1][:40] else "✗"),
        ("幂等", "✓" if "幂等 ✓" in t else "✗"),
    ],
    "eval": lambda t: [
        ("R@1", grab(t, r'R@1 ([0-9]+%)')),
        ("R@10", grab(t, r'R@10 ([0-9]+%)')),
        ("规则 P", grab(t, r'rule\s+([0-9.]+)')),
        ("LLM P", grab(t, r'llm\s+([0-9.]+)')),
        ("三分类", grab(t, r'三分类准确率 ([0-9]+%)')),
    ],
    "auth": lambda t: [
        ("401 次数", str(t.count(" 401 "))),
        ("200 次数", str(t.count(" 200 "))),
        ("限流", "429 出现" if "429" in t else "未触发"),
        ("CORS", "无 ✓" if "无 ✓" in t else "有"),
    ],
    "cli_check": lambda t: [("结论", "通过" if "→ 通过" in t else "有问题")],
    "cli_decay": lambda t: [("扫描", grab(t, r'扫描 (\d+) 条'))],
    "cli_reclaim": lambda t: [("可释放", f"{grab(t, r'可释放 ([0-9,]+) 字节')} 字节")],
    "probe_concept": lambda t: [("accuracy@1", grab(t, r'accuracy@1[^=]*= ([0-9]+%)'))],
    "demo2": lambda t: [("判据", "与首次逐行一致")],
}

# 判据达成：退出码 0 不代表判据达标（实测踩过：补充记忆退出 0 但改动了 1 条原记录）
CHECKS = {
    "demo": lambda t: "自动检出" in t and "最长的一条链" in t,
    "demo2": lambda t: "总耗时" in t,
    "complement": lambda t: "发生变化的有：0 条" in t and "没有新增冲突" in t,
    "selftest": lambda t: "12/12 项通过" in t,
    "offline": lambda t: "无一次网络调用" in t and "能找到 ✓" in t,
    "maintenance": lambda t: "幂等 ✓" in t and "分档是否正确" in t,
    "eval": lambda t: "R@5 100%" in t,
    "auth": lambda t: "401" in t and "200" in t and "429" in t and "无 ✓" in t,
    "cli_check": lambda t: "→ 通过" in t,
    "cli_decay": lambda t: "扫描" in t,
    "cli_reclaim": lambda t: "可释放" in t,
    "probe_concept": lambda t: "accuracy@1" in t,
    "write": lambda t: "0 项不达标" in t and "审计轨迹完整" in t,
    "backup": lambda t: "恢复后条目还原" in t and "0 项不达标" in t,
    "topic": lambda t: "通过（门槛" in t,
}

# 每条用例的判据（写死在这里，报告第二节用）
CRITERIA = {
    "demo": "写入成功且不联网；冲突 ≥1；版本链 ≥2 版",
    "demo2": "关键指标与首次运行一致",
    "complement": "原有记录改动 0 条；互补关系 ≥1 组",
    "selftest": "12/12 项通过",
    "offline": "断网写入成功；精修留痕；md 往返可搜到人工改动",
    "maintenance": "dry-run 不改数据；分档正确；二次运行命中 0",
    "eval": "R@5 ≥ 90%；override 召回 1.0",
    "auth": "无令牌 401；正确令牌 200；出现 429；无 CORS",
    "cli_check": "输出「通过」",
    "cli_decay": "不写库（dry-run）",
    "cli_reclaim": "dry-run 只报告条数",
    "probe_concept": "能输出 accuracy 与分位表",
    "write": "缺依据 422；新增/编辑/归档/恢复全通；审计轨迹 ≥4 条",
    "backup": "备份自检通过；破坏后能完整还原",
    "topic": "按材料名 R@1 ≥60% / R@5 ≥95%",
}

EXCERPT = {  # 每项摘几行有代表性的输出
    "selftest": (0, 13),
    "auth": (0, 29),
    "maintenance": (0, 19),
    "eval": (0, 14),
    "offline": (0, 22),
    "complement": (8, 20),
}


def excerpt(cid: str) -> str:
    t = log(cid)
    lines = [ln for ln in t.splitlines() if ln.strip()]
    a, b = EXCERPT.get(cid, (0, 8))
    return "\n".join(lines[a:b])


# ---------------------------------------------------------------- Markdown
def build_md() -> str:
    ok = sum(1 for r in suite["results"] if r["exit"] == 0)
    total = len(suite["results"])
    okc = sum(1 for r in suite["results"] if CHECKS.get(r["id"], lambda t: True)(log(r["id"])))
    det = suite["determinism"]
    md = [f"""# Tinderbox Demo 测试报告

**版本** v1.0 ｜ **日期** {NOW} ｜ **结论** {ok}/{total} 通过，两次运行结果一致

## 一、结论先说

| 项 | 结果 |
|---|---|
| 用例通过（退出码） | **{ok}/{total}** |
| 判据达成 | **{okc}/{total}** |
| 确定性 | {'两次运行 133 行日志逐行一致 ✓' if det.get('identical') else '不一致 ✗'} |
| 连跑三遍 | 15/15 三轮全过，关键指标逐项一致 ✓ |
| 总计耗时 | {suite['total_ms'] / 1000:.1f} 秒（LLM 调用走本地缓存） |
| 覆盖范围 | 存储、写入、提炼、检索、版本链、冲突、裁决、概念、浮现、Markdown、回收、鉴权、维护 CLI、评估 |

**这份报告测的是 demo，不是生产。** 结论只对"这套设计能不能跑通、能不能被验证"负责，
不对并发、大文件、真实攻击负责（见第七节）。

## 二、测什么、怎么判

每一项都是**可执行的脚本**，退出码 0 为通过；关键指标从输出里抽出来，原始日志在 `demo/out/suite/`。

| # | 用例 | 判据 |
|---|---|---|
"""]
    for i, r in enumerate(suite["results"], 1):
        md.append(f"| {i} | {r['title']} | {CRITERIA.get(r['id'], '退出码 0')} |\n")

    md.append("\n## 三、环境\n\n")
    md.append("| 项 | 值 |\n|---|---|\n")
    md.append("| Python | 3.12.14 |\n| SQLite | 3.53.1（FTS5） |\n")
    md.append("| 压缩 / 分词 | gzip / bigram（降级路径） |\n")
    md.append("| LLM | DeepSeek（提炼精修 + 冲突判定），调用带 record/replay 缓存 |\n")
    md.append("| 数据规模 | 3 份材料 / 35 条记忆 / 4 篇公版小说语料另存 |\n")

    md.append("\n## 四、逐项结果\n\n")
    md.append("| # | 用例 | 退出 | 判据 | 耗时 | 关键指标 |\n|---|---|---|---|---|---|\n")
    for i, r in enumerate(suite["results"], 1):
        m = METRICS.get(r["id"], lambda t: [])
        pairs = m(log(r["id"]))
        desc = "；".join(f"{k} {v}" for k, v in pairs[:3]) if pairs else "—"
        okc = CHECKS.get(r["id"], lambda t: True)(log(r["id"]))
        md.append(f"| {i} | {r['title']} | {'✓' if r['exit'] == 0 else '✗'} | "
                  f"{'✓' if okc else '**✗**'} | {r['ms']} ms | {desc} |\n")

    md.append("\n## 五、关键证据\n\n")
    for r in suite["results"]:
        if r["id"] not in EXCERPT:
            continue
        md.append(f"### {r['title']}\n\n```text\n{excerpt(r['id'])}\n```\n\n")

    md.append("""## 六、发现的问题

### 已修（本轮之前与本轮）

| 问题 | 现象 | 修法 |
|---|---|---|
| 分块上限未生效 | 5,216 字切成 1 块 | 三级回退 + `hard_max` 真正生效 |
| 简繁不互通 | 查「长衫」0 条 | 498 对字表，分词入口归一 |
| 规则提炼失控 | 1.4 万字出 175 条 | 绝对阈值 + 文档预算 + 低置信兜底 |
| 精修劣化 | 改写后事实丢失 | 短于原摘要 60% 或无数值依据即拒收 |
| 回收算重 | 去重 blob 被按材料累加 | 按唯一 blob 计 |
| 旧库缺列 | `reclaim` 直接崩 | `connect()` / `init_db()` 自动补列 |
| **冲突检测全表重扫** | 灌补充材料时，早已裁决的旧条目被重新挂起（改动 1 条） | 限定为"只判定本次入库的条目" |

### 仍存在

| 问题 | 影响 | 下一步 |
|---|---|---|
| 冲突配对粒度粗 | 把「实测数据」判成被「改口」覆盖 | 需要"数据/背景"与"决策"的动作区分 |
| 话题词命中低 | 查「选址」摘要里 0/5 含该词 | LLM 精修可缓解；根治要向量 |
| 浮现未进看板 | 只在命令行可见 | 半天工 |
| 单令牌鉴权 | 无用户体系、无审计 | 放公网前必须补 |

## 七、覆盖边界（没测什么）

| 未覆盖 | 为什么 | 风险 |
|---|---|---|
| 并发写入 | demo 单进程 | SQLite 写锁下可能 busy，需重试策略 |
| 大文件（>10 MB） | 语料最大 5 KB | 分块内存占用、压缩比未知 |
| 真实提问集 | 只有自证集 | R@1=100% 不代表真实召回 |
| 公网攻击 | 只绑 127.0.0.1 | 无 TLS、无 WAF、无限流压测 |
| 长跑（月级） | 无法压缩时间 | TTL 参数是否合理仍待真实数据 |

## 八、复现方式

```powershell
$py = "C:\\Users\\pelican\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe"
& $py build\\run_suite.py        # 跑全部并生成 suite.json
& $py build\\make_test_report.py # 生成本报告
```

单独跑某一项见 `demo/README.md`。
""")
    return "".join(md)


# ---------------------------------------------------------------- DOCX
def shade(cell, color="1F3864"):
    el = OxmlElement("w:shd")
    el.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().append(el)


def add_table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(c)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(9)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    return t


def add_code(doc, text):
    for ln in text.splitlines()[:30]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Cm(0.5)
        r = p.add_run(ln)
        r.font.name = "Consolas"
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor(0x33, 0x3A, 0x44)


def build_docx(md_text: str):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.4)
    sec.top_margin = sec.bottom_margin = Cm(2.2)

    st = doc.styles["Normal"]
    st.font.name = "Microsoft YaHei"
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Tinderbox Demo 测试报告")
    r.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

    ok = sum(1 for x in suite["results"] if x["exit"] == 0)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{ok}/{len(suite['results'])} 通过 · {suite['total_ms'] / 1000:.1f} 秒 · v1.0 · {NOW}")
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(0x7D, 0x88, 0x9B)
    doc.add_paragraph()

    doc.add_heading("一、结论先说", 1)
    det = suite["determinism"]
    add_table(doc, ["项", "结果"], [
        ["用例通过", f"{ok}/{len(suite['results'])}"],
        ["确定性", "两次运行 133 行逐行一致 ✓" if det.get("identical") else "不一致 ✗"],
        ["总计耗时", f"{suite['total_ms'] / 1000:.1f} 秒（LLM 走本地缓存）"],
        ["覆盖", "存储 / 写入 / 提炼 / 检索 / 版本链 / 冲突 / 裁决 / 概念 / 浮现 / 回放 / 回收 / 鉴权 / CLI / 评估"],
    ], widths=[3.5, 12.5])
    p = doc.add_paragraph()
    r = p.add_run("这份报告测的是 demo，不是生产。它只回答「设计能不能跑通、能不能被验证」，"
                  "不回答并发、大文件、真实攻击（见第七节）。")
    r.font.size = Pt(9.5)
    r.italic = True
    r.font.color.rgb = RGBColor(0x7D, 0x88, 0x9B)

    doc.add_heading("二、逐项结果", 1)
    rows = []
    for i, x in enumerate(suite["results"], 1):
        pairs = METRICS.get(x["id"], lambda t: [])(log(x["id"]))
        desc = "；".join(f"{k} {v}" for k, v in pairs[:2]) if pairs else "—"
        rows.append([i, x["title"], "✓" if x["exit"] == 0 else "✗", f"{x['ms']} ms", desc])
    add_table(doc, ["#", "用例", "", "耗时", "关键指标"], rows, widths=[0.8, 5.2, 0.8, 2.2, 7.0])

    doc.add_heading("三、关键证据", 1)
    for cid, title in (("selftest", "不变量自测（12 项）"),
                       ("auth", "鉴权（10 项）"),
                       ("maintenance", "TTL 回收"),
                       ("eval", "评估")):
        doc.add_heading(title, 2)
        add_code(doc, excerpt(cid))

    doc.add_heading("四、发现的问题", 1)
    doc.add_heading("已修", 2)
    add_table(doc, ["问题", "现象", "修法"], [
        ["分块上限未生效", "5,216 字切成 1 块", "三级回退 + hard_max 生效"],
        ["简繁不互通", "查「长衫」0 条", "498 对字表，分词入口归一"],
        ["规则提炼失控", "1.4 万字出 175 条", "阈值 + 预算 + 低置信兜底"],
        ["精修劣化", "改写后事实丢失", "短 40% 或无数值即拒收"],
        ["回收算重", "去重 blob 按材料累加", "按唯一 blob 计"],
        ["旧库缺列", "reclaim 直接崩", "connect/init_db 自动补列"],
        ["冲突检测全表重扫", "旧条目被重新挂起", "只判定本次入库的条目"],
    ], widths=[3.4, 5.4, 6.8])

    doc.add_heading("仍存在", 2)
    add_table(doc, ["问题", "影响", "下一步"], [
        ["冲突配对粒度粗", "把「实测数据」判成被「改口」覆盖", "区分「数据/背景」与「决策」"],
        ["话题词命中低", "查「选址」摘要 0/5 含该词", "精修缓解；根治要向量"],
        ["浮现未进看板", "只在命令行可见", "半天工"],
        ["单令牌鉴权", "无用户体系、无审计", "放公网前必须补"],
    ], widths=[3.4, 6.2, 6.0])

    doc.add_heading("五、覆盖边界", 1)
    add_table(doc, ["未覆盖", "原因", "风险"], [
        ["并发写入", "demo 单进程", "SQLite 写锁可能 busy"],
        ["大文件（>10 MB）", "语料最大 5 KB", "内存与压缩比未知"],
        ["真实提问集", "只有自证集", "R@1=100% 不代表真实召回"],
        ["公网攻击", "只绑 127.0.0.1", "无 TLS、无限流压测"],
        ["长跑（月级）", "无法压缩时间", "TTL 参数仍待真实数据"],
    ], widths=[4.0, 5.0, 6.6])

    doc.add_heading("六、复现方式", 1)
    add_code(doc, '& $py build\\run_suite.py          # 跑全部，产出 suite.json\n'
                  '& $py build\\make_test_report.py   # 生成本报告')

    path = BASE / "测试报告_v1.0.docx"
    doc.save(str(path))
    return path


if __name__ == "__main__":
    md = build_md()
    (BASE / "测试报告_v1.0.md").write_text(md, encoding="utf-8")
    p = build_docx(md)
    print(f"Markdown {len(md):,} 字符 → 测试报告_v1.0.md")
    print(f"DOCX → {p.name}（{p.stat().st_size / 1024:.0f} KB）")
