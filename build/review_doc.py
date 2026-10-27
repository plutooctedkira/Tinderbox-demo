"""方案体检：交叉引用、常量矛盾、伪代码、编码噪点。"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

MD = Path(r"E:\记忆库\Tinderbox_记忆库完整方案_v2.15.md")
text = MD.read_text(encoding="utf-8")
lines = text.split("\n")

# ---------------- 1. 标题清单 ----------------
heading = re.compile(r"^(#{2,4})\s+(\d+(?:\.\d+)*)\s*(.*)$")
sections: dict[str, str] = {}
for ln in lines:
    m = heading.match(ln)
    if m:
        sections[m.group(2)] = m.group(3)
print(f"标题 {len(sections)} 个，最深 {max(len(k.split('.')) for k in sections)} 层")

# ---------------- 2. 交叉引用 ----------------
ref = re.compile(r"见\s*(\d+(?:\.\d+)+)|第\s*(\d+)\s*章")
missing = defaultdict(list)
for i, ln in enumerate(lines, 1):
    for m in ref.finditer(ln):
        sid = m.group(1)
        if sid:
            parts = sid.split(".")
            ok = sid in sections or (".".join(parts[:2]) in sections
                                     and parts[0] in {k.split(".")[0] for k in sections})
            if not ok:
                missing[sid].append(i)
print(f"\n【一】交叉引用指向不存在的章节：{len(missing)} 个")
for sid, where in sorted(missing.items(), key=lambda x: -len(x[1]))[:12]:
    print(f"  {sid:<10} 被引用 {len(where)} 次，行 {where[:6]}")

# ---------------- 3. 常量矛盾 ----------------
CONST = re.compile(
    r"`([A-Z][A-Z0-9_]{2,})`[^|\n]{0,12}?[=：:]\s*`?([\d.]+)`?|"
    r"([A-Z][A-Z0-9_]{2,})\s*=\s*([\d.]+)")
vals: dict[str, set[str]] = defaultdict(set)
for ln in lines:
    for m in CONST.finditer(ln):
        if m.group(1):
            vals[m.group(1)].add(m.group(2))
        elif m.group(3):
            vals[m.group(3)].add(m.group(4))
conflict = {k: v for k, v in vals.items() if len(v) > 1}
print(f"\n【二】同一常量出现多个值：{len(conflict)} 处")
for k, v in sorted(conflict.items()):
    print(f"  {k:<22}{sorted(v)}")

# ---------------- 4. 代码块 ----------------
fences = [i for i, ln in enumerate(lines) if ln.strip().startswith("```")]
blocks = []
for a, b in zip(fences[::2], fences[1::2]):
    lang = lines[a].strip().strip("`").strip() or "(none)"
    body = lines[a + 1:b]
    blocks.append((a + 1, lang, body))
print(f"\n【三】代码块 {len(blocks)} 个")
kinds = defaultdict(int)
for _, lang, _ in blocks:
    kinds[lang] += 1
print("  语言分布:", dict(kinds))
PSEUDO = re.compile(r"(\.\.\.|…|省略|伪代码|示意|略\)|TODO|<[^>\n]{2,}>)")
pseudo = [(ln, lang, next(l for l in body if PSEUDO.search(l)))
          for ln, lang, body in blocks if any(PSEUDO.search(l) for l in body)]
print(f"  其中含省略/伪代码标记：{len(pseudo)} 个")
for ln, lang, sample in pseudo[:14]:
    print(f"    行{ln:>5} [{lang:<8}] {sample.strip()[:56]}")

# ---------------- 5. 编码噪点 ----------------
print("\n【四】可疑字符/排版")
SUSPECT = [
    ("替换字符 ?", re.compile(r"\ufffd")),
    ("康熙部首", re.compile(r"[\u2f00-\u2fdf]")),
    ("全角空格", re.compile(r"\u3000")),
    ("零宽字符", re.compile(r"[\u200b-\u200f\ufeff]")),
    ("CJK 之间夹空格", re.compile(r"[\u4e00-\u9fff]\s[\u4e00-\u9fff]")),
    ("重复标点", re.compile(r"[，。；：]{2,}")),
    ("半角标点接中文", re.compile(r"[\u4e00-\u9fff][,;:!?][\u4e00-\u9fff]")),
]
for name, pat in SUSPECT:
    hits = [(i, ln.strip()[:70]) for i, ln in enumerate(lines, 1) if pat.search(ln)]
    if hits:
        print(f"  {name}: {len(hits)} 处")
        for i, s in hits[:3]:
            print(f"      行{i:>5}  {s}")
    else:
        print(f"  {name}: 0")
