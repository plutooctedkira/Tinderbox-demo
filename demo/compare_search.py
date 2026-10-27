"""同一批查询，比规则版与 LLM 版的检索命中。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402

BASE = Path(__file__).resolve().parent / "out"
QUERIES = ["选址", "止损线", "雨天", "创业园区", "沉没成本"]


def open_db(tag):
    tb.DB_PATH = BASE / f"cmp_{tag}.db"
    return tb.init_db()


for tag, label in (("rule", "规则版"), ("llm", "LLM 版")):
    conn = open_db(tag)
    print(f"\n【{label}】")
    for q in QUERIES:
        hits = tb.search(conn, q, top_k=3)
        first = hits[0]["l1_summary"][:34] if hits else "—"
        in_self = sum(1 for h in hits if q in h["l1_summary"])
        print(f"  {q:<8}命中 {len(hits)} 条 ｜摘要里含该词 {in_self}/{max(len(hits),1)} ｜top1: {first}")
    conn.close()
