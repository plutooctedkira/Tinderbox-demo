import pathlib
import re
import re
import unicodedata

MD = pathlib.Path(r"E:\记忆库\Tinderbox_记忆库完整方案_v2.28.md")
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

# ---------------------------------------------------------------- 一致性检查
# 非必要 / 未启用的功能，不应出现在建表区与配置表里（除非该行明确标了"预留/未启用"）
# 严格档：连表/配置都不该出现（未排期）
DEFERRED_STRICT = {
    "向量": ("memory_vectors", "EMBED_", "sqlite_vec"),
}
# 提示档：非必要但设计完整，允许出现，只提示（音频/导出/迁移属于这类）
DEFERRED_SOFT = {
    "音频": ("memory_media", "asr_adapter", "media_ingest"),
    "Obsidian 导出": ("exporter", "OBSIDIAN_"),
    "数据迁移": ("migrations/v2_",),
}
DEFERRED = {**DEFERRED_STRICT, **DEFERRED_SOFT}
MARK = ("预留", "未启用", "非必要", "不建表", "已砍", "不做")

# 只在"建表区"（5.x）与"配置表"（附录 A）里查
zones = []
in_zone = False
for i, ln in enumerate(lines):
    if re.match(r"^### 5\.\d|^## 附录 A", ln):
        in_zone = True
        continue
    if re.match(r"^## ", ln) and not ln.startswith("## 附录 A"):
        in_zone = False
    if in_zone:
        zones.append((i + 1, ln))

violations = []
for feat, toks in DEFERRED.items():
    for lineno, ln in zones:
        if not any(t in ln for t in toks):
            continue
        # 同行或前后 6 行内出现"预留/未启用"标记即放过
        nearby = " ".join(x[1] for x in zones if abs(x[0] - lineno) <= 6)
        if any(m in ln for m in MARK) or any(m in nearby for m in MARK):
            continue
        violations.append((feat, lineno, ln.strip()[:72]))

hard = [v for v in violations if v[0] in DEFERRED_STRICT]
soft = [v for v in violations if v[0] not in DEFERRED_STRICT]
print(f"\n[一致性] 未排期功能混入 schema/配置：{len(hard)}（硬性）· {len(soft)}（仅提示）")
for feat, lineno, txt in hard[:6]:
    print(f"  ✗ {feat} @ 行{lineno}: {txt}")
if soft:
    print(f"  · 提示：{'、'.join(sorted({v[0] for v in soft}))} 的内容仍留在正文（非必要但已设计）")
