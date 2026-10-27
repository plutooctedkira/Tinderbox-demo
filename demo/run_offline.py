"""证明三件事：断网也能写、联网后异步精修、Markdown 可读可改。

跑法：python demo/run_offline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402

BASE = Path(__file__).resolve().parent
TEXT = (BASE / "sample.txt").read_text(encoding="utf-8")


def rule(t=""):
    print(f"\n── {t} " + "─" * max(0, 60 - len(t) * 2))


def main():
    db = BASE / "out" / "offline.db"
    for f in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
        f.unlink(missing_ok=True)
    tb.DB_PATH = db
    conn = tb.init_db(reset=True)

    # ---------- ① 断网写入 ----------
    import api_client
    real_chat = api_client.chat

    def offline(*a, **k):
        raise RuntimeError("network is down")

    api_client.chat = offline
    rule("① 断网：写入必须成功")
    import time
    t = time.time()
    res = tb.ingest(conn, TEXT, title="露营咖啡车项目记录")
    ms = (time.time() - t) * 1000
    states = [r[0] for r in conn.execute(
        "SELECT extract_state FROM memory_entries")]
    print(f"  写入 {len(res['entries'])} 条，{ms:.0f} ms，无一次网络调用")
    print(f"  状态分布：{ {s: states.count(s) for s in set(states)} }")
    print(f"  检索仍可用：查「大学城」→ {len(tb.search(conn, '大学城'))} 条")

    # ---------- ② 联网后精修 ----------
    api_client.chat = real_chat
    rule("② 联网：后台精修（异步，不阻塞）")
    before = [r[0] for r in conn.execute(
        "SELECT l1_summary FROM memory_entries ORDER BY row_id LIMIT 3")]
    out = tb.refine(conn, limit=5)
    print(f"  扫描 {out['scanned']} 条，精修 {out['refined']} 条，失败 {out['failed']} 条")
    print(f"  留痕记录：{conn.execute('SELECT count(*) FROM memory_revisions').fetchone()[0]} 条")
    for r in conn.execute("SELECT old_summary, new_summary FROM memory_revisions LIMIT 2"):
        print(f"    旧：{r['old_summary'][:40]}")
        print(f"    新：{r['new_summary'][:40]}")

    # ---------- ③ 主动浮现 ----------
    rule("③ 对话开头：主动浮现")
    ctx = tb.active_context(conn, k=3)
    print(f"  浮现 {len(ctx['memories'])} 条 · 待裁决 {ctx['pending_conflicts']}"
          f" · 未精修 {ctx['provisional']}")
    for m in ctx["memories"]:
        print(f"    {m['score']:.2f}  {m['l1_summary'][:38]}")
        print(f"          └ {m['why']}")

    # ---------- ④ Markdown 镜像 ----------
    rule("④ Markdown：人可读、可编辑、可重建")
    path = BASE / "out" / "memory.md"
    tb.write_markdown(conn, path)
    text = path.read_text(encoding="utf-8")
    print(f"  已导出 {path.name}，{len(text)} 字符，{text.count(chr(10) + '- **')} 条记忆")
    print("  头几行：")
    for ln in text.splitlines()[:8]:
        print("    " + ln[:78])

    # 模拟人手改一条，再重建
    target = next(ln for ln in text.splitlines() if ln.strip().startswith("- 摘要："))
    edited = text.replace(target, target + "（人工校对）", 1)
    path.write_text(edited, encoding="utf-8")
    db2 = BASE / "out" / "offline_rebuilt.db"
    for f in (db2, Path(str(db2) + "-wal"), Path(str(db2) + "-shm")):
        f.unlink(missing_ok=True)
    tb.DB_PATH = db2
    conn2 = tb.init_db(reset=True)
    out2 = tb.rebuild_from_markdown(conn2, path)
    hits = tb.search(conn2, "人工校对")
    print(f"  从 md 重建：扫描 {out2['scanned']} 条，导入 {out2['imported']} 条")
    ok = any("人工校对" in h["l1_summary"] for h in hits)
    print(f"  人工改的那条{'能找到 ✓' if ok else '没找到 ✗'}："
          f"{hits[0]['l1_summary'][:44] if hits else '—'}")

    conn.close()
    conn2.close()


if __name__ == "__main__":
    main()
