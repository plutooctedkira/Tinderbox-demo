"""标定：按「材料名」找，能不能找到那份材料里的记忆。

这是最接近真实用法的一组查询——用户想不起来原话，只记得"那是在哪份笔记里"。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb

import argparse

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
args = ap.parse_args()
root = Path(args.data).expanduser()
tb.DB_PATH = root / "memory.db"
tb.ARCHIVE = root / "l0"
conn = tb.connect()

docs = conn.execute("SELECT doc_id, title FROM memory_documents ORDER BY title").fetchall()
hit1 = hit5 = total = 0
misses = []
for d in docs:
    q = tb.title_words(d["title"]) or d["title"]
    if not q:
        continue
    total += 1
    hits = tb.search(conn, q, mode="hybrid", top_k=5)
    ids = [h["entry_id"] for h in hits]
    owner = {r["entry_id"] for r in conn.execute(
        "SELECT entry_id FROM memory_entries WHERE doc_id=?", (d["doc_id"],))}
    if ids and ids[0] in owner:
        hit1 += 1
    if owner & set(ids):
        hit5 += 1
    else:
        misses.append((d["title"], q, len(hits)))

print(f"材料 {total} 份 · 查询=材料名")
print(f"  R@1 {hit1 / total:.0%}   R@5 {hit5 / total:.0%}")
if misses:
    print("  没召回的材料：")
    for title, q, n in misses[:8]:
        print(f"    {title}  ← 查「{q}」命中 {n} 条")
conn.close()
