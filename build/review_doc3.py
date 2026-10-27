"""方案体检 第三轮：章节体重、数量口径是否一致、路线图投入。"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

MD = Path(r"E:\记忆库\Tinderbox_记忆库完整方案_v2.15.md")
lines = MD.read_text(encoding="utf-8").split("\n")

# 各章行数
chap = re.compile(r"^##\s+(\d+)\s+(.*)$")
idx = [(i, chap.match(ln).group(1), chap.match(ln).group(2))
       for i, ln in enumerate(lines) if chap.match(ln)]
print("【一】各章体重（行数 / 表格数 / 代码块）")
for k, (i, num, title) in enumerate(idx):
    end = idx[k + 1][0] if k + 1 < len(idx) else len(lines)
    seg = lines[i:end]
    tables = sum(1 for ln in seg if ln.startswith("|") and ln.count("|") > 2)
    codes = sum(1 for ln in seg if ln.strip().startswith("```")) // 2
    print(f"  第{num:>2}章 {title[:22]:<24}{end - i:>5} 行  表 {tables:>4}  码 {codes:>3}")

# 数量口径
print("\n【二】带数量的口径（同一说法出现多个数就是矛盾）")
PAT = [
    (r"(\d+)\s*个页面", "页面数"),
    (r"(\d+)\s*个面板", "面板数"),
    (r"(\d+)\s*张表", "表数"),
    (r"(\d+)\s*个模块", "模块数"),
    (r"(\d+)\s*人日", "人日"),
    (r"(\d+)\s*个触发器", "触发器"),
    (r"(\d+)\s*条(?:不变量|用例)", "用例数"),
]
for pat, name in PAT:
    hits = [(i, m.group(1), lines[i].strip()[:60])
            for i, ln in enumerate(lines)
            for m in [re.search(pat, ln)] if m]
    vals = Counter(h[1] for h in hits)
    flag = "⚠ 多个口径" if len(vals) > 1 else ""
    print(f"  {name:<10}{dict(vals)}  {flag}")
    if len(vals) > 1:
        for i, v, s in hits[:6]:
            print(f"      行{i + 1:>5} [{v}] {s}")

# 人日拆分
print("\n【三】工作量拆分")
for i, ln in enumerate(lines, 1):
    if "人日" in ln and ("|" in ln or "合计" in ln):
        print(f"  行{i:>5} {ln.strip()[:100]}")

# 路线图阶段
print("\n【四】阶段划分")
for i, ln in enumerate(lines, 1):
    if re.match(r"^\|\s*\*?\*?P\d", ln.strip()) or "里程碑" in ln:
        print(f"  行{i:>5} {ln.strip()[:110]}")
