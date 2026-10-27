import pathlib
import re
import re
import unicodedata

MD = pathlib.Path(r"E:\记忆库\Tinderbox_实施手册_v1.0.md")
doc = MD.read_text(encoding="utf-8")
lines = doc.split("\n")

fence = False
problems, h, tables, rows, wide, stray = [], {}, 0, 0, [], []
i = 0
while i < len(lines):
    line = lines[i]
    if line.lstrip().startswith("```"):
        fence = not fence
        i += 1
        continue
    if fence:
        w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line)
        if w > 105:
            wide.append((i + 1, w, line[:80]))
        i += 1
        continue
    if line.startswith("#"):
        m = re.match(r"^(#{1,6})\s", line)
        if m:
            h[len(m.group(1))] = h.get(len(m.group(1)), 0) + 1
    if '"' in re.sub(r"`[^`]+`", "", line):
        stray.append((i + 1, line[:80]))
    if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:\-|]+\|[\s:\-|]*$", lines[i + 1]):
        tables += 1
        ncols = len(re.split(r"(?<!\\)\|", line.strip().strip("|")))
        j = i + 2
        while j < len(lines) and "|" in lines[j] and lines[j].strip():
            cells = re.split(r"(?<!\\)\|", lines[j].strip().strip("|"))
            rows += 1
            if len(cells) != ncols:
                problems.append(f"L{j+1}: {len(cells)} vs {ncols}")
            j += 1
        i = j
        continue
    i += 1

heads = set()
fence = False
for line in lines:
    if line.lstrip().startswith("```"):
        fence = not fence
        continue
    if fence:
        continue
    m = re.match(r"^#{2,4}\s+(\d+(?:\.\d+)*)\s", line)
    if m:
        heads.add(m.group(1))

print(f"chars={len(doc)} lines={len(lines)} tables={tables} rows={rows}")
print("fence balanced:", not fence)
print("headings:", dict(sorted(h.items())))
print("table cell mismatches:", len(problems), problems[:5])
print("code lines > 105 cols:", len(wide), wide[:6])
print("prose lines with ASCII quotes:", len(stray), stray[:5])
# 之前只认 `### ` 三级标题，漏掉了 `#### ` 四级小节，导致 6.10.2/6.10.3 长期误报 MISSING
for need in ("5.7", "6.6", "6.10.2", "6.10.3", "8.4", "8.5", "15.1", "附录D"):
    if need == "附录D":
        present = "## 附录 D" in doc
    else:
        present = any(re.match(rf"^#{{2,4}}\s*{re.escape(need)}\b", l) for l in lines)
    print(f"  section {need if need != '附录D' else '附录 D'}: {'ok' if present else 'MISSING'}")
