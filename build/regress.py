"""重构后回归：日志结构必须和重构前一致（忽略随机 ID、数字、横线长度）。"""
import re
from pathlib import Path

OUT = Path(r"E:\记忆库\demo\out")
ID = re.compile(r"\b(mem|c|g|k|r)-[0-9a-f]{6,}\b")
NUM = re.compile(r"\d+(?:\.\d+)?")
DASH = re.compile(r"─{3,}")


def norm(p: Path) -> list[str]:
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        ln = ID.sub("ID", ln)
        ln = DASH.sub("─…", ln)
        out.append(NUM.sub("#", ln.rstrip()))
    return out


for before, after in (("run.before.log", "run.log"), ("complement.before.log", "complement.log")):
    a, b = norm(OUT / before), norm(OUT / after)
    same = a == b
    print(f"{before:<26} → {after:<16} 行数 {len(a)} vs {len(b)}  "
          f"{'✓ 结构完全一致' if same else '✗ 有差异'}")
    if not same:
        shown = 0
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y and shown < 3:
                print(f"  第 {i + 1} 行:\n    旧 {x[:88]}\n    新 {y[:88]}")
                shown += 1
        if len(a) != len(b):
            print("  行数不等")
