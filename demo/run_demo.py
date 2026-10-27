"""一键演示：L0 落盘 → 分块 → 提 L1 → 中文检索 → 回原文 → 归档 → 版本链 → 星网。

跑法：  python demo/run_demo.py
输出同时写到 demo/out/run.log（UTF-8），便于留存与比对。

每个步骤是一个函数，只依赖 ctx 字典；想单独调试某一步，直接调它即可。
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tb  # noqa: E402
from demo_util import capture, kv, rule  # noqa: E402

BASE = Path(__file__).resolve().parent
LOG = BASE / "out" / "run.log"


def pick(conn, query, must, mode="active"):
    hits = tb.search(conn, query, mode=mode, top_k=20)
    for h in hits:
        if must in h["l1_summary"]:
            return h
    if hits:
        return hits[0]
    raise SystemExit(f"检索失败：query={query!r} 无结果")


def spread_dates(conn, doc_id, days):
    """把这份材料的条目按原文位置铺到最近 N 天，只为让时间轴可见。"""
    rows = conn.execute("SELECT row_id, l0_offset FROM memory_entries WHERE doc_id=?",
                        (doc_id,)).fetchall()
    span = max(r["l0_offset"] for r in rows) or 1
    base = datetime.now(timezone.utc) - timedelta(days=days)
    for r in rows:
        ts = base + timedelta(days=float(days) * r["l0_offset"] / span)
        conn.execute("UPDATE memory_entries SET created_at=? WHERE row_id=?",
                     (ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", r["row_id"]))


# ---------------------------------------------------------------- 步骤
def step_env(ctx):
    info = tb.env_info()
    ctx["info"] = info
    kv("Python / SQLite", f"{info['python']} / {info['sqlite']}")
    kv("压缩", f"{info['codec']}" + ("（zstandard 缺失，自动退 gzip）" if info["codec"] == "gzip" else ""))
    kv("分词", f"{info['tokenizer']}" + ("（jieba 缺失，自动退 bigram）" if info["tokenizer"] == "bigram" else ""))
    kv("数据库", info["db"])


def step_create_db(ctx):
    conn = tb.init_db(reset=True)
    ctx["conn"] = conn
    kv("表", "documents / blobs / groups / entries")
    kv("FTS", "active + history 双索引")
    kv("触发器", "3 个：插入/更新/删除 → 按 status 路由")


def step_l0(ctx):
    conn = ctx["conn"]
    text = (BASE / "sample.txt").read_text(encoding="utf-8")
    ctx["text"] = text
    t = time.time()
    doc_id = tb.put_document(conn, text, title="露营咖啡车项目记录", source="import")
    ctx["doc_id"] = doc_id
    ctx["l0_ms"] = (time.time() - t) * 1000
    row = conn.execute("SELECT * FROM memory_documents WHERE doc_id=?", (doc_id,)).fetchone()
    kv("材料字数", f"{row['char_count']:,} 字")
    kv("原文 / 压缩后", f"{row['raw_size']:,} → {row['compressed_size']:,} 字节"
                        f"（{row['raw_size'] / row['compressed_size']:.2f}:1，{ctx['info']['codec']}）")
    kv("落盘", f"archive/l0/{row['blob_hash'][:2]}/…{row['blob_hash'][-8:]}")
    kv("耗时", f"{ctx['l0_ms']:.1f} ms")
    print("  → 一份材料一个文件，不分块；分块只发生在“读窗口”里。")


def pick_extractor(ctx):
    """能连上 LLM 就用 LLM，否则退回规则版（红线：任何失败都不能让入库失败）。"""
    if ctx.get("force_rule"):
        return None, "规则提炼（--rule 强制）"
    try:
        import llm_ingest
        llm_ingest.api_client.chat("ok", max_tokens=1)      # 探活
    except Exception as e:
        return None, f"规则提炼（LLM 不可用：{type(e).__name__}）"
    ctx["judge_fns"] = [tb.judge, llm_ingest.judge_llm]     # 规则 + LLM 取并集
    return (lambda t2, c, chunk_start: llm_ingest.extract_llm(t2, c, chunk_start=chunk_start)[0],
            "LLM 提炼")


def step_l1(ctx):
    conn, text = ctx["conn"], ctx["text"]
    extractor, label = pick_extractor(ctx)
    ctx["extractor"] = extractor
    chunks = tb.split_semantic(text)
    print(f"  切成 {len(chunks)} 块（段落优先，目标 700 字）")
    for i, (a, b) in enumerate(chunks):
        head = text[a:a + 22].replace("\n", " ")
        print(f"    #{i}  [{a:>5},{b:>5})  {b - a:>4} 字  {head}…")

    t = time.time()
    # 写入路径只用本地规则：15 ms 量级、确定、不依赖任何外部服务。
    # 断网时这一步照常成功——记忆先落地，质量后补。
    res = tb.ingest(conn, text, doc_id=ctx["doc_id"], judge_fns=ctx.get("judge_fns"))
    ctx["res"] = res
    dt = (time.time() - t) * 1000
    spread_dates(conn, ctx["doc_id"], 30)

    print(f"\n  写入 {len(res['entries'])} 条 L1（规则提炼，{dt:.1f} ms，**不联网**）：")
    for e in res["entries"]:
        ts = conn.execute("SELECT created_at FROM memory_entries WHERE entry_id=?",
                          (e["entry_id"],)).fetchone()[0][:10]
        print(f"    [{e['category']:<10}] {ts}  {e['l1_summary'][:30]}")
    if extractor is not None:                               # 有 LLM 才精修
        r = tb.refine(conn, limit=8)
        print(f"  ↻ 后台精修：扫描 {r['scanned']} 条 → 采纳 {r['refined']} 条、"
              f"驳回 {r['failed']} 条（丢事实或没写出依据）")
        print("    写入与精修是两条路：断网时写入照常成功，精修等联网再补。")

    print(f"  ⏱ 材料本身是一份跨月记录，这里按原文位置把 {len(res['entries'])} 条铺到最近 30 天，")
    print("    只为让时间轴可见（真实实现取写入时刻）。")


def step_search(ctx):
    conn = ctx["conn"]
    for q in ("止损线", "冷萃", "创业园区"):
        hits = tb.search(conn, q)
        print(f"\n  查「{q}」→ {len(hits)} 条")
        for h in hits[:3]:
            print(f"    {h['score']:.3f}  rel={h['s_rel']:.2f} rec={h['s_rec']:.2f}  "
                  f"{h['created_at'][:10]}  {h['l1_summary'][:32]}")

    hits = tb.search(conn, "选址")
    print(f"\n  查「选址」→ {len(hits)} 条（这是标题词，只在关键词列命中）")
    for h in hits[:3]:
        print(f"    {h['score']:.3f}  {h['l1_summary'][:38]}")
    print("  ⚠ 这 5 条的摘要里都没有“选址”二字，排序被 BM25 的长度偏置带偏了。")
    print("    这是规则提炼的已知短板：方案里靠 LLM 提炼（摘要自带话题）和向量检索来补。")


def step_span(ctx):
    conn = ctx["conn"]
    target = pick(conn, "首站放在大学城", "大学城")
    span = tb.get_span(conn, target["entry_id"], before=50, after=50)
    kv("条目", target["entry_id"])
    kv("L0 区间", f"[{span['offset']}, {span['offset'] + span['length']})  长 {span['length']} 字")
    print("  原文（含前后各 50 字）：")
    for line in span["text"].split("\n"):
        if line.strip():
            print(f"    │ {line.strip()}")
    print("  → 解压只取这几百字，不把整份材料塞回主库。")


def step_archive(ctx):
    conn = ctx["conn"]
    victim = pick(conn, "冷萃", "冷萃")
    tb.archive(conn, victim["entry_id"])
    kv("active 模式", f"{len(tb.search(conn, '冷萃', mode='active'))} 条（已沉下去）")
    kv("history 模式", f"{len(tb.search(conn, '冷萃', mode='history'))} 条（仍可追溯）")
    print("  → 归档 ≠ 丢失：条目从 active 索引挪到 history 索引，原文一字未动。")


def step_conflict(ctx):
    conn = ctx["conn"]
    conflicts = tb.list_conflicts(conn)
    print(f"  入库时自动检出 {len(conflicts)} 处冲突：\n")
    for c in conflicts:
        print(f"    冲突 {c['conflict_id']}  [{c['relation']}]  置信 {c['confidence']:.2f}")
        print(f"      旧  {c['old_entry_id']}  {next(e['l1_summary'] for e in ctx['res']['entries'] if e['entry_id'] == c['old_entry_id'])[:40]}")
        print(f"      新  {c['new_entry_id']}  {next(e['l1_summary'] for e in ctx['res']['entries'] if e['entry_id'] == c['new_entry_id'])[:40]}")
        print(f"      判定原因：{c['reason']}")
        print(f"      当前状态：新条目已被挂成 pending_merge，没有自动覆盖旧条目。")
    print("  → 高危动作不交给规则/模型，只挂起等人裁决（方案 6.9）。")

    if not conflicts:
        return
    conflicts.sort(key=lambda c: conn.execute(
        "SELECT l0_offset FROM memory_entries WHERE entry_id=?",
        (c["old_entry_id"],)).fetchone()[0])
    c = conflicts[0]
    print(f"\n  人工裁决 {c['conflict_id']} → supersede（旧版作废，新版接管）")
    tb.resolve_conflict(conn, c["conflict_id"], "supersede")
    grp = conn.execute("SELECT memory_group_id FROM memory_entries WHERE entry_id=?",
                       (c["old_entry_id"],)).fetchone()[0]
    for node in tb.chain(conn, grp):
        mark = "●" if node["status"] == "active" else "○"
        print(f"    {mark} v{node['version_no']}  {node['status']:<11}{node['l1_summary'][:36]}")
        if node["version_no"] == 1 and node["context"]:
            print(f"        前因：{node['context'][:64]}")
    print("  → 裁决后新旧合成一条版本链：旧版 superseded 并移入 history，新版 active。")
    rest = len(tb.list_conflicts(conn))
    if rest:
        print(f"  其余 {rest} 处仍挂起（pending_merge），看板里是橙色「待裁决」——"
              f"高危动作不会因为你没看就自动执行。")


MONTH = {"三月": 3, "四月": 4, "五月": 5, "六月": 6, "七月": 7,
         "八月": 8, "九月": 9, "十月": 10}


def step_chain(ctx):
    conn = ctx["conn"]
    text2 = (BASE / "sample2.txt").read_text(encoding="utf-8")
    res2 = tb.ingest(conn, text2, title="豆子供货商决策记录",
                     judge_fns=ctx.get("judge_fns"))
    if ctx.get("extractor") is not None:
        tb.refine(conn, limit=6)
    ids2 = {e["entry_id"] for e in res2["entries"]}
    spread_dates(conn, res2["doc_id"], 210)

    # 这份材料的时间线索是明写的（三月/四月/六月/九月），按它回填更贴合叙事
    for e in res2["entries"]:
        # 取“最先出现”的月份词：四月那段结尾提到“推翻三月的选择”，不能因此算成三月
        cand = [(e["l1_summary"].find(w), m) for w, m in MONTH.items()
                if w in e["l1_summary"]]
        if cand:
            mon = min(cand)[1]
            conn.execute("UPDATE memory_entries SET created_at=? WHERE entry_id=?",
                         (f"2026-{mon:02d}-15T09:00:00.000Z", e["entry_id"]))
    print(f"  灌入第二份材料：{len(res2['entries'])} 条，自动检出 {len(res2['conflicts'])} 处冲突")

    # 按原文顺序裁决，让链条线性生长
    def offset(eid):
        return conn.execute("SELECT l0_offset FROM memory_entries WHERE entry_id=?",
                            (eid,)).fetchone()[0]

    pend = [c for c in tb.list_conflicts(conn)
            if c["old_entry_id"] in ids2 and c["new_entry_id"] in ids2]
    pend.sort(key=lambda c: (offset(c["old_entry_id"]), offset(c["new_entry_id"])))
    # 留最后一处不裁：它属于"看板上等你点"的那类，正好演示人工审核
    for c in pend[:-1]:
        tb.resolve_conflict(conn, c["conflict_id"], "supersede")
    left = len(pend) - len(pend[:-1])
    print(f"  按原文顺序裁决 {len(pend) - left} 处 → supersede；"
          f"留 {left} 处待人工裁决（看板「冲突」里点）\n")

    chains = tb.list_chains(conn)
    if not chains:
        print("  本轮没有形成版本链（没检出覆盖关系）")
        return
    best = max(chains, key=lambda g: len(g["nodes"]))
    print(f"  最长的一条链：{len(best['nodes'])} 个版本")
    for n in best["nodes"]:
        gap = "·" if n["gap_days"] is None else f"+{round(n['gap_days'])}天"
        mark = "●" if n["status"] == "active" else "○"
        print(f"    {mark} v{n['version_no']}  {gap:<7}{n['l1_summary'][:40]}")
        if n["version_no"] == 1 and n["context"]:
            print(f"        前因：{n['context'][:64]}")
    print("  → 链首自带前因，后续版本只需要交代相对上一版改了什么。")
    print("  → 版本号越大越新；间隔是判据：改得越密，说明这件事还没定下来。")


def step_net(ctx):
    conn = ctx["conn"]
    root_name = "咖啡车生意"
    root_id = tb.ensure_concept(conn, root_name, None, 0)
    hubs = [x["name"] for x in tb.concept_tree(conn)
            if x["parent_id"] is None and x["name"] != root_name]
    with tb.tx(conn):
        for h in hubs:
            conn.execute("UPDATE memory_concepts SET parent_id=?, level=1 WHERE name=?",
                         (root_id, h))
        # 子节点顺延一层
    tb.relevel(conn)                       # 挂完父节点，层级要重算
    by_parent: dict = {}
    for c in tb.concept_tree(conn):
        by_parent.setdefault(c["parent_id"], []).append(c)
    for node in by_parent.get(None, []):
        print(f"  {node['name']}（{node['direct']} 条自身 · {node['children']} 个子概念）")
        for child in by_parent.get(node["concept_id"], []):
            print(f"    ├─ {child['name']}（{child['direct']} 条）")
            for leaf in by_parent.get(child["concept_id"], []):
                print(f"    │    · {leaf['name']}（{leaf['direct']} 条）")
    hits = tb.concept_entries(conn, root_name)
    print(f"\n  问「{root_name}」→ 汇总 {len(hits)} 条，跨了 {len({h['category'] for h in hits})} 个类别：")
    for h in hits[:5]:
        print(f"    [{h['category']:<10}] {h['l1_summary'][:34]}")
    print("  → 豆子和选址本来互不相干，挂到同一个概念下就能一起被捞出来。")


def step_summary(ctx):
    conn = ctx["conn"]
    st = tb.stats(conn)
    kv("材料 / 条目", f"{st['documents']} 份 / {st['entries']} 条")
    kv("状态分布", f"active {st['active']} · pending {st['pending_merge']} · "
                   f"archived {st['archived']} · superseded {st['superseded']}")
    kv("L0 冷存", f"{st['l0_bytes']:,} 字节（原文 {st['l0_raw']:,}）")
    kv("FTS 行数", f"active {st['fts_active']} · history {st['fts_history']}")
    kv("主库体积", f"{st['db_bytes']:,} 字节")
    kv("总耗时", f"{(time.time() - ctx['t0']) * 1000:.0f} ms")
    try:
        import api_client
        st = api_client.cache_stats()
        if st["hit"] or st["miss"]:
            kv("LLM 调用", f"命中缓存 {st['hit']} · 实际请求 {st['miss']}")
    except Exception:
        pass


STEPS = [
    ("环境", step_env),
    ("建库", step_create_db),
    ("① 材料整体落盘（L0）", step_l0),
    ("② 语义分块 + 逐块提炼 L1", step_l1),
    ("③ 中文检索（score = 0.60·相关性 + 0.25·新鲜度 + 0.15·权重）", step_search),
    ("④ 按 offset 回到 L0 原文", step_span),
    ("⑤ 归档一条：看双索引各司其职", step_archive),
    ("⑥ 冲突检测：两条记忆打架时怎么办", step_conflict),
    ("⑦ 同一件事改四次口：链会有多长", step_chain),
    ("⑧ 星网：把两个话题挂到同一个概念下", step_net),
    ("汇总", step_summary),
]


def main(stop_after: str | None = None, *, force_rule: bool = False):
    """stop_after：跑到指定步骤就停（调试用），前面的步骤照常执行。"""
    ctx: dict = {"t0": time.time(), "force_rule": force_rule}
    with capture(LOG):
        for title, fn in STEPS:
            rule(title)
            fn(ctx)
            if stop_after and (stop_after in title or stop_after == fn.__name__):
                break

        rule()
        print("数据库：demo/out/memory.db    原文：demo/out/archive/l0/")
        print("看板：  python demo/web.py  →  http://127.0.0.1:8777")

    if "conn" in ctx:
        ctx["conn"].close()


if __name__ == "__main__":
    # 用法：python demo/run_demo.py            跑全流程（有 key 就用 LLM 提炼）
    #      python demo/run_demo.py --rule       强制规则提炼
    #      python demo/run_demo.py ②            跑到第②步就停（排查用）
    args = [a for a in sys.argv[1:] if a != "--rule"]
    main(args[0] if args else None, force_rule="--rule" in sys.argv)
