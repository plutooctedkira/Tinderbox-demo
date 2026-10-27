"""清理：删缓存；把 v2.9–v2.14 的松散文件收进 zip（校验后再删原文件）。"""
from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(r"E:\记忆库")
HIST = ROOT / "历史归档"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------- 1) 缓存 ----------
removed = 0
for d in ROOT.rglob("__pycache__"):
    if d.is_dir():
        n = len(list(d.glob("*")))
        shutil.rmtree(d)
        removed += n
print(f"删除 __pycache__：{removed} 个文件")

# ---------- 2) 历史归档打包 ----------
loose = sorted([p for p in HIST.iterdir()
                if p.suffix in {".md", ".docx"} and p.stem.startswith("v2.")])
if not loose:
    print("历史归档里没有松散版本，跳过")
else:
    zip_path = HIST / "Tinderbox_历史版本_v2.9-v2.14.zip"
    before = {p.name: sha(p) for p in loose}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in loose:
            z.write(p, arcname=p.name)
    # 校验：每个文件都能完整读出，且哈希一致
    ok = True
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        for name, h in before.items():
            if name not in names:
                ok = False
                print(f"  ✗ 压缩包缺 {name}")
                continue
            if hashlib.sha256(z.read(name)).hexdigest() != h:
                ok = False
                print(f"  ✗ {name} 哈希不一致")
    if ok:
        for p in loose:
            p.unlink()
        print(f"打包 {len(before)} 个文件 → {zip_path.name}"
              f"（{zip_path.stat().st_size/1024/1024:.2f} MB），校验收到的 {len(names)} 项全部一致，已删除原文件")
    else:
        zip_path.unlink()
        print("校验失败，已撤销压缩包，原文件保留")

# ---------- 3) 结果 ----------
files = [p for p in ROOT.rglob("*") if p.is_file()]
print(f"\n剩余文件 {len(files)} 个，总计 {sum(p.stat().st_size for p in files)/1024/1024:.1f} MB")
print("\n历史归档：")
for p in sorted(HIST.iterdir()):
    print(f"  {p.name:<38}{p.stat().st_size/1024/1024:>7.2f} MB")
