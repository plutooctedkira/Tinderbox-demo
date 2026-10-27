"""按材料名检索的标定，带门槛（不达标退出码 1）。

门槛：R@1 ≥ 60%、R@5 ≥ 95%。低于这个数说明"想不起原话、只记得在哪份笔记里"这种
最常见的找法不好用。
"""
import shutil
import subprocess
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent
PY = sys.executable
DATA = DEMO / "out" / "topiccase"

sys.path.insert(0, str(DEMO))
import tb  # noqa: E402

shutil.rmtree(DATA, ignore_errors=True)
subprocess.run([PY, str(DEMO / "tbc.py"), "--data", str(DATA), "init"], capture_output=True)
for f in sorted((DEMO / "seed_notes").glob("*.md")):
    subprocess.run([PY, str(DEMO / "tbc.py"), "--data", str(DATA), "ingest", str(f)],
                   capture_output=True)

tb.DB_PATH = DATA / "memory.db"
tb.ARCHIVE = DATA / "l0"
conn = tb.connect()
docs = conn.execute("SELECT doc_id, title FROM memory_documents ORDER BY title").fetchall()

hit1 = hit5 = total = 0
for d in docs:
    q = tb.title_words(d["title"])
    if not q:
        continue
    total += 1
    ids = [h["entry_id"] for h in tb.search(conn, q, mode="hybrid", top_k=5)]
    owner = {r["entry_id"] for r in conn.execute(
        "SELECT entry_id FROM memory_entries WHERE doc_id=?", (d["doc_id"],))}
    if ids and ids[0] in owner:
        hit1 += 1
    if owner & set(ids):
        hit5 += 1
conn.close()

r1, r5 = (hit1 / total if total else 0), (hit5 / total if total else 0)
print(f"材料 {total} 份 · 查询=材料名")
print(f"  R@1 {r1:.0%}   R@5 {r5:.0%}")
good = r1 >= 0.60 and r5 >= 0.95
print(f"\n{'通过' if good else '不达标'}（门槛 R@1 60% / R@5 95%）")
sys.exit(0 if good else 1)
