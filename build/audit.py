"""清点：重复文件、临时产物、历史归档里到底有什么。"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"E:\记忆库")
SKIP_DIRS = {".git", "__pycache__"}

files = [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.parts) & SKIP_DIRS)]

by_hash: dict[str, list[Path]] = defaultdict(list)
for p in files:
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    by_hash[h].append(p)

dups = {h: ps for h, ps in by_hash.items() if len(ps) > 1}
print(f"文件总数 {len(files)}，总大小 {sum(p.stat().st_size for p in files)/1024/1024:.1f} MB\n")

print("【一】内容完全相同的重复文件")
if not dups:
    print("  没有")
for h, ps in dups.items():
    size = ps[0].stat().st_size
    print(f"  {size/1024:>8.1f} KB × {len(ps)} 份  ({h})")
    for p in ps:
        print(f"      {p.relative_to(ROOT)}")

print("\n【二】临时产物 / 缓存")
junk = [p for p in files if p.suffix in {".pyc", ".pyo", ".tmp", ".bak", ".orig"}
        or p.name.startswith("~$") or p.name.startswith("p_") and p.suffix == ".py"]
pycache = [p for p in ROOT.rglob("__pycache__") if p.is_dir()]
if not junk and not pycache:
    print("  没有")
for p in junk:
    print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size} B)")
for d in pycache:
    n = len(list(d.glob("*")))
    print(f"  {d.relative_to(ROOT)}/  （目录，{n} 个文件）")

print("\n【三】历史归档里有什么")
hist = ROOT / "历史归档"
if hist.exists():
    for p in sorted(hist.iterdir()):
        print(f"  {p.name:<34}{p.stat().st_size/1024/1024:>7.2f} MB")
    loose = [p for p in hist.iterdir() if p.suffix in {".md", ".docx"}]
    stems = {p.stem.rsplit("_v", 1)[-1] for p in loose}
    zips = [p for p in hist.iterdir() if p.suffix == ".zip"]
    if zips and stems:
        print(f"  → 松散版本 {len(stems)} 个：{', '.join(sorted(stems))}")
        print(f"  → 压缩包 {len(zips)} 个（内容是否与松散文件重叠需单独确认）")

print("\n【四】各目录体积")
for d in sorted({p.parent for p in files}):
    tot = sum(p.stat().st_size for p in files if p.parent == d)
    print(f"  {str(d.relative_to(ROOT)):<28}{tot/1024:>10.1f} KB  ({len([p for p in files if p.parent == d])} 个)")
