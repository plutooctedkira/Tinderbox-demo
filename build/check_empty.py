"""检查一：空库。所有读接口都要能活着返回空，而不是 500 或崩。"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"E:\记忆库\demo")
import tb

DATA = Path(r"E:\记忆库\.empty")
shutil.rmtree(DATA, ignore_errors=True)
subprocess.run([sys.executable, r"E:\记忆库\demo\tbc.py", "--data", str(DATA), "init"],
               capture_output=True)
tb.DB_PATH = DATA / "memory.db"
tb.ARCHIVE = DATA / "l0"
conn = tb.connect()

cases = [
    ("stats", lambda: tb.stats(conn)),
    ("active_context", lambda: tb.active_context(conn, 5)),
    ("list_chains", lambda: tb.list_chains(conn)),
    ("concept_tree", lambda: tb.concept_tree(conn)),
    ("search", lambda: tb.search(conn, "任何词")),
    ("decay(dry)", lambda: tb.decay(conn, dry_run=True)),
    ("reclaim(dry)", lambda: tb.reclaim(conn, dry_run=True)),
]
for name, fn in cases:
    try:
        out = fn()
        kind = type(out).__name__
        size = len(out) if hasattr(out, "__len__") else "-"
        print(f"  ✓ {name:<15}{kind} len={size}")
    except Exception as e:
        print(f"  ✗ {name:<15}{type(e).__name__}: {e}")

# 空库上做一次写入，再读
r = tb.ingest(conn, "最后决定：先做空库测试——因为要确认第一条记忆能进来。")
print(f"\n  空库首条写入：{len(r['entries'])} 条")
print(f"  再读 stats：{tb.stats(conn)}")
conn.close()
