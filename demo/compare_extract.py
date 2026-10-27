"""对照：同一份材料，规则提炼 vs LLM 提炼。

跑法：python demo/compare_extract.py
输出：两条路径的 L1 逐条对照 + 质量指标 + 耗时
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402
import llm_ingest  # noqa: E402

BASE = Path(__file__).resolve().parent
TEXT = (BASE / "sample.txt").read_text(encoding="utf-8")


def fresh_db(tag: str):
    tb.DB_PATH = BASE / "out" / f"cmp_{tag}.db"
    for p in (tb.DB_PATH, Path(str(tb.DB_PATH) + "-wal"), Path(str(tb.DB_PATH) + "-shm")):
        p.unlink(missing_ok=True)
    return tb.init_db(reset=True)


def metrics(entries: list[dict]) -> dict:
    n = len(entries)
    summ = [e["l1_summary"] for e in entries]
    has_reason = sum(1 for s in summ if re.search(r"因为|由于|理由是|原因是", s))
    has_ctx = sum(1 for e in entries if (e.get("context") or "").strip())
    avg_len = sum(len(s) for s in summ) / max(n, 1)
    trunc = sum(1 for s in summ if s.endswith("…"))
    return {"条数": n, "带依据": f"{has_reason}/{n}", "带前因": f"{has_ctx}/{n}",
            "平均字数": f"{avg_len:.0f}", "被截断": f"{trunc}/{n}"}


def show(title: str, entries: list[dict], ms: float):
    print(f"\n{'=' * 78}\n{title}   共 {len(entries)} 条，耗时 {ms:.0f} ms\n{'=' * 78}")
    for i, e in enumerate(entries, 1):
        print(f"\n[{i}] {e['category']:<10} {e.get('topic') or '-'}")
        print(f"    摘要：{e['l1_summary']}")
        if (e.get("context") or "").strip():
            print(f"    前因：{e['context']}")
        if e.get("quote"):
            print(f"    引文：{e['quote'][:60]}")


def main():
    # 规则版
    conn = fresh_db("rule")
    t = time.time()
    res = tb.ingest(conn, TEXT, title="规则提炼")
    rule_ms = (time.time() - t) * 1000
    rule_entries = [{"category": e["category"], "l1_summary": e["l1_summary"],
                     "context": e.get("context", ""), "topic": e.get("topic"),
                     "quote": ""} for e in res["entries"]]
    conn.close()

    # LLM 版
    conn = fresh_db("llm")
    t = time.time()
    try:
        res2 = llm_ingest.ingest_llm(conn, TEXT, title="LLM 提炼")
        llm_ms = (time.time() - t) * 1000
        llm_entries = res2["entries"]
        err = None
    except Exception as e:
        llm_entries, llm_ms, err = [], 0, f"{type(e).__name__}: {e}"
    conn.close()

    show("【规则提炼】", rule_entries, rule_ms)
    if err:
        print(f"\n【LLM 提炼】失败：{err}")
        return 1
    show("【LLM 提炼】", llm_entries, llm_ms)

    print(f"\n{'=' * 78}\n【对比】\n{'=' * 78}")
    m1, m2 = metrics(rule_entries), metrics(llm_entries)
    keys = list(m1)
    print(f"  {'指标':<10}{'规则版':<14}{'LLM 版':<14}")
    for k in keys:
        print(f"  {k:<10}{str(m1[k]):<14}{str(m2[k]):<14}")
    print(f"  {'耗时':<10}{f'{rule_ms:.0f} ms':<14}{f'{llm_ms:.0f} ms':<14}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
