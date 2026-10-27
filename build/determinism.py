"""验证 record/replay 的确定性：两次 LLM 运行的日志应当逐行一致（忽略 ID/数字/耗时）。"""
import re
from pathlib import Path

OUT = Path(r"E:\记忆库\demo\out")
ID = re.compile(r"\b(mem|c|g|k|r)-[0-9a-f]{6,}\b")
NUM = re.compile(r"\d+(?:\.\d+)?")
DASH = re.compile(r"─{3,}")


def norm(p):
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        ln = ID.sub("ID", ln)
        ln = DASH.sub("─…", ln)
        out.append(NUM.sub("#", ln.rstrip()))
    return out


a = norm(OUT / "run.rec2.log")
b = norm(OUT / "run.log")
same = a == b
print(f"两次运行：{len(a)} 行 vs {len(b)} 行  {'✓ 完全一致（可复现）' if same else '✗ 有差异'}")
if not same:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            print(f"  第 {i + 1} 行:\n    A {x[:80]}\n    B {y[:80]}")
            break

cache = list((OUT / "llm_cache").glob("*.json"))
size = sum(p.stat().st_size for p in cache) / 1024
print(f"缓存文件 {len(cache)} 个，共 {size:.1f} KB")
