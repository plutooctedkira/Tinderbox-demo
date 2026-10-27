"""体检：这 128 页里，多少是能指导写代码的，多少是自说自话。"""
import re
from pathlib import Path

MD = Path(r"E:\记忆库\Tinderbox_记忆库完整方案_v2.19.md")
lines = MD.read_text(encoding="utf-8").split("\n")

chap = re.compile(r"^##\s+(.+)$")
idx = [(i, chap.match(ln).group(1).strip()) for i, ln in enumerate(lines) if chap.match(ln)]
rows = []
total = len(lines)
for k, (i, title) in enumerate(idx):
    end = idx[k + 1][0] if k + 1 < len(idx) else total
    seg = lines[i:end]
    chars = sum(len(x) for x in seg)
    tables = sum(1 for x in seg if x.startswith("|"))
    codes = sum(1 for x in seg if x.strip().startswith("```")) // 2
    rows.append((title, end - i, chars, tables, codes))

body = [r for r in rows if not r[0].startswith("附录")]
appendix = [r for r in rows if r[0].startswith("附录")]

print(f"总行数 {total} · 总字符 {sum(len(x) for x in lines):,}\n")
print(f"{'章节':<26}{'行':>6}{'字符':>9}{'表行':>7}{'代码块':>7}")
for t, n, c, tb, cd in rows:
    print(f"{t[:24]:<26}{n:>6}{c:>9,}{tb:>7}{cd:>7}")

bc = sum(r[2] for r in body)
ac = sum(r[2] for r in appendix)
print(f"\n正文 {bc:,} 字符（{bc / (bc + ac):.0%}）  附录 {ac:,} 字符（{ac / (bc + ac):.0%}）")

# 附录 D 是修订史，单独算
d = [r for r in rows if "附录 D" in r[0]]
if d:
    print(f"其中「附录 D 修订史」{d[0][2]:,} 字符，占全文 {d[0][2] / (bc + ac):.0%}")

# 关键字统计：多少行是"实施性"的
impl = sum(1 for x in lines if re.search(r"```|^\|", x))
print(f"\n代码/表格行 {impl}（{impl / total:.0%}）  纯文字 {total - impl}（{1 - impl / total:.0%}）")
