"""验证 TTL 回收：已核对/未核对两档、dry-run 不写、真删后账目对得上。

跑法：python demo/run_maintenance.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402

BASE = Path(__file__).resolve().parent


def rule(t=""):
    print(f"\n── {t} " + "─" * max(0, 56 - len(t) * 2))


def age_entries(conn, doc_id: str, days: int):
    ts = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    conn.execute("UPDATE memory_entries SET created_at=? WHERE doc_id=?", (ts, doc_id))


def main():
    db = BASE / "out" / "ttl.db"
    for f in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
        f.unlink(missing_ok=True)
    tb.DB_PATH = db
    conn = tb.init_db(reset=True)

    # 两份材料：A 被核对过，B 从未核对
    text = (BASE / "sample.txt").read_text(encoding="utf-8")
    a = tb.ingest(conn, text, title="材料 A（已核对，200 天）")
    b = tb.ingest(conn, text, title="材料 B（未核对，800 天）")
    # C：未核对、400 天——两档的分界线就在这里（<730 应保留）
    c = tb.ingest(conn, text + "\n\n（C 的补充段落，用于区分内容）", title="材料 C（未核对，400 天）")

    with tb.tx(conn):
        for r in conn.execute("SELECT entry_id FROM memory_entries WHERE doc_id=?",
                              (a["doc_id"],)):
            conn.execute("UPDATE memory_entries SET verified_at=?, verified_by='human' "
                         "WHERE entry_id=?", (tb.now(), r["entry_id"]))
        # 两份都变"死"（全部归档），并分别回拨到 200 天 / 800 天
        conn.execute("UPDATE memory_entries SET status='archived' WHERE doc_id=?", (a["doc_id"],))
        conn.execute("UPDATE memory_entries SET status='archived' WHERE doc_id=?", (b["doc_id"],))
    age_entries(conn, a["doc_id"], 200)     # 已核对档 180 天 → 该回收
    age_entries(conn, b["doc_id"], 800)     # 未核对档 730 天 → 该回收
    age_entries(conn, c["doc_id"], 400)     # 未核对档 730 天 → **不该回收**

    st0 = tb.stats(conn)
    rule("① 回收前")
    print(f"  材料 {st0['documents']} 份 · L0 {st0['l0_bytes']:,} 字节")

    rule("② dry-run（不该动数据）")
    out = tb.reclaim(conn, dry_run=True)
    print(f"  命中 {out['victims']} 份：零引用 {len(out['zero_ref'])} · "
          f"引用全死 {len(out['all_dead'])} · 硬 TTL {len(out['expired'])}")
    print(f"  可释放 {out['freed_bytes']:,} 字节")
    st1 = tb.stats(conn)
    print(f"  数据未变：材料 {st1['documents']} 份，L0 {st1['l0_bytes']:,} 字节 "
          f"{'✓' if st1['documents'] == st0['documents'] else '✗'}")

    rule("③ 真执行")
    out2 = tb.reclaim(conn, dry_run=False)
    st2 = tb.stats(conn)
    print(f"  删除 {out2['victims']} 份 · 材料 {st2['documents']} 份 · "
          f"L0 {st2['l0_bytes']:,} 字节（释放 {st0['l0_bytes'] - st2['l0_bytes']:,}）")
    tier_ok = st2["documents"] == 1
    print(f"  分档是否正确：剩 {st2['documents']} 份（应为 1，即 400 天未核对那份）"
          f" {'✓' if tier_ok else '✗'}")
    print(f"  压缩块剩 {st2['blobs']} 个（应为 1）")

    rule("④ 账目与结构")
    neg = conn.execute("SELECT count(*) c FROM memory_blobs WHERE ref_count<0").fetchone()["c"]
    orphan = conn.execute(
        "SELECT count(*) c FROM memory_entries e LEFT JOIN memory_documents d "
        "ON d.doc_id=e.doc_id WHERE e.doc_id IS NOT NULL AND d.doc_id IS NULL").fetchone()["c"]
    print(f"  负引用 {neg} · 孤儿条目 {orphan} · FTS active {st2['fts_active']} "
          f"/ history {st2['fts_history']}")

    rule("⑤ 再跑一次（必须无事可做）")
    out3 = tb.reclaim(conn, dry_run=False)
    print(f"  命中 {out3['victims']} 份 → {'幂等 ✓' if out3['victims'] == 0 else '✗ 不幂等'}")

    conn.close()


if __name__ == "__main__":
    main()
