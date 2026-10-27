"""维护 CLI：cron 的唯一入口。

用法：
  python demo/maintenance.py stats
  python demo/maintenance.py decay            # 默认 dry-run
  python demo/maintenance.py decay --apply
  python demo/maintenance.py reclaim          # 默认 dry-run
  python demo/maintenance.py reclaim --apply
  python demo/maintenance.py check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402


def cmd_stats(conn, args) -> int:
    st = tb.stats(conn)
    for k, v in st.items():
        print(f"  {k:<16}{v}")
    return 0


def cmd_decay(conn, args) -> int:
    out = tb.decay(conn, dry_run=not args.apply)
    print(f"  扫描 {out['scanned']} 条 · 权重下降 {out['decayed']} 条 · "
          f"可归档 {out['would_archive']} 条" + ("（dry-run，未写入）" if out["dry_run"] else ""))
    return 0


def cmd_reclaim(conn, args) -> int:
    out = tb.reclaim(conn, dry_run=not args.apply, shrink=args.shrink)
    print(f"  零引用 {len(out['zero_ref'])} · 引用全死 {len(out['all_dead'])} · "
          f"硬 TTL {len(out['expired'])} · 瘦身 {len(out['shrunk'])}")
    print(f"  可释放 {out['freed_bytes']:,} 字节 / {out['victims']} 份材料"
          + ("（dry-run，未写入）" if out["dry_run"] else "（已执行）"))
    return 0


def cmd_check(conn, args) -> int:
    """结构自检：孤儿引用、权重越界、索引与状态不一致。"""
    bad = 0
    orphans = conn.execute(
        "SELECT count(*) c FROM memory_entries e LEFT JOIN memory_documents d "
        "ON d.doc_id = e.doc_id WHERE e.doc_id IS NOT NULL AND d.doc_id IS NULL").fetchone()["c"]
    print(f"  孤儿条目（指向不存在的材料）: {orphans}")
    bad += orphans
    zero = conn.execute(
        "SELECT count(*) c FROM memory_blobs WHERE ref_count < 0").fetchone()["c"]
    print(f"  负引用计数: {zero}")
    bad += zero
    st = tb.stats(conn)
    live = st["active"] + st["pending_merge"]
    print(f"  FTS 一致性: active {st['fts_active']}/{live} · "
          f"history {st['fts_history']}/{st['archived'] + st['superseded']}")
    bad += abs(st["fts_active"] - live)
    print(f"  → {'通过' if bad == 0 else f'发现 {bad} 处问题'}")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Tinderbox 维护命令")
    ap.add_argument("cmd", choices=["stats", "decay", "reclaim", "check"])
    ap.add_argument("--apply", action="store_true", help="真的执行（默认 dry-run）")
    ap.add_argument("--shrink", action="store_true", help="同时瘦身原文（不可逆）")
    args = ap.parse_args()

    conn = tb.connect()
    try:
        return {"stats": cmd_stats, "decay": cmd_decay,
                "reclaim": cmd_reclaim, "check": cmd_check}[args.cmd](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
