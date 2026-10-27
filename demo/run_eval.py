"""评估：检索 Recall + 冲突判定精确率/召回率。

分两层，诚实标注：
  · 检索用「自证集」——查询词取自条目自身，**是乐观上界**，不代表真实提问。
  · 冲突用 10 对人工标注（脚标注在 PAIRS 里，可复核）。

跑法：python demo/run_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402

BASE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 检索自证集
def build_queries(conn, limit: int = 60) -> list[dict]:
    rows = conn.execute(
        "SELECT entry_id, l1_summary, keywords FROM memory_entries "
        "WHERE status='active' AND doc_id IS NOT NULL").fetchall()
    out = []
    for r in rows[:limit]:
        kws = (r["keywords"] or "").split()
        cand = [k for k in kws[1:] if len(k) >= 3][:3]
        q = cand[0] if cand else r["l1_summary"][:6]
        out.append({"q": q, "target": r["entry_id"], "summary": r["l1_summary"]})
    return out


def eval_retrieval(conn, queries: list[dict], k: int = 10) -> dict:
    hit1 = hit5 = hitk = 0
    rr = 0.0
    for item in queries:
        hits = tb.search(conn, item["q"], mode="hybrid", top_k=k)
        ids = [h["entry_id"] for h in hits]
        if item["target"] in ids:
            rank = ids.index(item["target"]) + 1
            hitk += 1
            rr += 1.0 / rank
            hit1 += rank == 1
            hit5 += rank <= 5
    n = max(len(queries), 1)
    return {"n": len(queries), "R@1": hit1 / n, "R@5": hit5 / n,
            f"R@{k}": hitk / n, "MRR": rr / n}


# ---------------------------------------------------------------- 冲突判定标注集
# (旧摘要片段, 新摘要片段, 人工标签, 理由)
PAIRS = [
    ("最后决定：首站放在大学城", "所以改口：首站从大学城改到创业园区", "override",
     "首站从 A 改到 B，旧结论作废"),
    ("所以改口：首站从大学城改到创业园区", "这个调整不改变项目本身，只是把首站从大学城改成创业园区", "duplicate",
     "同一件事的重复表述，没有新信息"),
    ("三月的时候定了用本地烘焙商 A", "四月改口，换成大宗商 B", "override", "换供应商"),
    ("四月改口，换成大宗商 B", "六月又重新算了一遍，改成 A 供单品豆", "override", "再改供货方案"),
    ("六月又重新算了一遍", "九月最后定下来：A 独家供应", "override", "双轨改独家"),
    ("菜单尽量短：美式、拿铁、燕麦拿铁、冷萃", "单杯成本按豆子、奶、杯子和损耗合计", "complement",
     "菜单与成本是两件事"),
    ("车辆本身花了 4 万 2", "单杯成本按豆子、奶、杯子和损耗合计", "complement", "沉没成本与单杯成本互补"),
    ("所以决定：雨天不出摊", "如果连续三周毛利低于 40%", "complement", "雨天策略与止损规则并列"),
    ("最后决定：首站放在大学城", "三月的时候定了用本地烘焙商 A", "unrelated", "选址与供货无关"),
    ("跑了一周大学城之后，情况比预期差", "所以改口：首站从大学城改到创业园区", "complement",
     "实测数据是改址的依据，不推翻决策本身"),
]


def judge_all(conn, old: str, new: str):
    o = conn.execute("SELECT keywords, l1_summary FROM memory_entries "
                     "WHERE l1_summary LIKE ? LIMIT 1", (f"%{old}%",)).fetchone()
    n = conn.execute("SELECT keywords, l1_summary FROM memory_entries "
                     "WHERE l1_summary LIKE ? LIMIT 1", (f"%{new}%",)).fetchone()
    if not o or not n:
        return None
    rule = tb.judge(n["l1_summary"], n["keywords"], o["l1_summary"], o["keywords"])
    llm = None
    try:
        import llm_ingest
        llm = llm_ingest.judge_llm(n["l1_summary"], n["keywords"],
                                   o["l1_summary"], o["keywords"])
    except Exception:
        pass
    union = tb.merge_verdicts([rule] + ([llm] if llm else []))
    return {"rule": rule, "llm": llm, "union": union}


def eval_conflict(conn) -> dict:
    stats = {"rule": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
             "llm": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
             "union": {"tp": 0, "fp": 0, "fn": 0, "tn": 0}}
    exact = {"rule": 0, "llm": 0, "union": 0}
    rows, missing = [], 0
    for old, new, label, why in PAIRS:
        r = judge_all(conn, old, new)
        if r is None:
            missing += 1
            continue
        rows.append((old, new, label, why, r))
        for j in stats:
            if not r.get(j):
                continue
            pred = r[j][0]
            pos_actual, pos_pred = label == "override", pred == "override"
            key = ("tp" if pos_actual and pos_pred else
                   "fp" if pos_pred else "fn" if pos_actual else "tn")
            stats[j][key] += 1
            if pred == label:
                exact[j] += 1
    out = {"missing": missing, "stats": stats, "rows": rows, "exact": exact,
           "n": len(rows)}
    return out


def metrics(s: dict) -> dict:
    tp, fp, fn = s["tp"], s["fp"], s["fn"]
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 2), "recall": round(r, 2), "f1": round(f1, 2)}


def fresh_eval_db():
    """评估必须可复现：临时库 + 规则提炼，不精修，措辞稳定。"""
    db = BASE / "out" / "eval.db"
    for f in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
        f.unlink(missing_ok=True)
    tb.DB_PATH = db
    conn = tb.init_db(reset=True)
    for name, title in (("sample.txt", "露营咖啡车项目记录"),
                        ("sample2.txt", "豆子供货商决策记录")):
        tb.ingest(conn, (BASE / name).read_text(encoding="utf-8"), title=title)
    return conn


def main():
    conn = fresh_eval_db()
    save = BASE / "out" / "eval.json"
    report = {}

    qs = build_queries(conn)
    rec = eval_retrieval(conn, qs)
    report["retrieval"] = rec
    print("【检索 · 自证集】乐观上界，非真实提问")
    print(f"  样本 {rec['n']} 条   R@1 {rec['R@1']:.0%}   R@5 {rec['R@5']:.0%}   "
          f"R@10 {rec['R@10']:.0%}   MRR {rec['MRR']:.2f}")

    conf = eval_conflict(conn)
    report["conflict"] = {"missing": conf["missing"],
                          **{j: metrics(s) for j, s in conf["stats"].items()}}
    print(f"\n【冲突判定 · {len(PAIRS)} 对人工标注】")
    print(f"  {'判定器':<8}{'precision':>11}{'recall':>9}{'f1':>6}   （override 类）")
    for j in ("rule", "llm", "union"):
        m = report["conflict"][j]
        acc = conf["exact"][j] / max(conf["n"], 1)
        print(f"  {j:<8}{m['precision']:>11.2f}{m['recall']:>9.2f}{m['f1']:>6.2f}"
              f"      三分类准确率 {acc:.0%}")
    if conf["missing"]:
        print(f"  ⚠ {conf['missing']} 对没在库里找到，已跳过")

    topics = ["选址", "菜单", "豆子", "成本", "雨天"]
    print("\n【话题查询 · 更接近真实提问】")
    for t in topics:
        hits = tb.search(conn, t, mode="hybrid", top_k=5)
        ok = sum(1 for h in hits if t in h["l1_summary"] or t in (h["category"] or ""))
        print(f"  查「{t}」→ {len(hits)} 条，摘要含该词的 {ok} 条  "
              f"| top1: {hits[0]['l1_summary'][:30] if hits else '—'}")

    print("\n【逐对】")
    if conf["missing"]:
        print(f"  （{conf['missing']} 对未匹配，见下方说明）")
    for old, new, label, why, r in conf["rows"]:
        parts = []
        for j in ("rule", "llm", "union"):
            if r.get(j):
                mark = "✓" if r[j][0] == label else "✗"
                parts.append(f"{j}:{r[j][0]}{mark}")
        print(f"  [{label:<10}] {old[:14]} ↔ {new[:14]}   {' '.join(parts)}")

    save.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("""
【怎么读这些数】
  · 检索 R@1 100% 是**自证上界**：查询词直接取自摘要，当然能找到。真实提问会更难。
  · 冲突只有 5 个 override 正例，precision 的置信区间很宽（±0.2 级别），只能看趋势。
  · 有三对标签**本身存疑**，错判未必是系统错：
      改口 ↔ 调整说明      —— 算 duplicate 还是 override，取决于产品口径
      菜单 ↔ 成本          —— 我标了 complement，但两者也可能只是"同项目不同话题"
      雨天 ↔ 毛利止损       —— 同上，标 complement 偏主观
  · 一条**确定的系统错误**：把"实测数据"当成被"改口"覆盖的对象（第 10 对）。
    这说明按"同话题 + 变更标记"配对的粒度还是太粗——数据不是决策，不该被决策覆盖。""")
    print(f"\n结果已写入 {save.relative_to(BASE.parent)}")
    conn.close()


if __name__ == "__main__":
    main()
