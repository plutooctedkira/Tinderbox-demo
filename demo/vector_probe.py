"""对照实验：同一个任务，bigram 基线 vs LSA 向量。

跑的是两件今天卡住的事：
  ① 概念挂靠准确率
  ② 冲突配对——「改口」能不能认对「决定」这个爹
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

import tb  # noqa: E402
from vectors import VectorSpace, centroid, cosine  # noqa: E402


def load(conn):
    rows = conn.execute(
        "SELECT entry_id, l1_summary FROM memory_entries "
        "WHERE status IN ('active','pending_merge') ORDER BY row_id").fetchall()
    truth = {}
    for r in rows:
        c = conn.execute(
            "SELECT c.concept_id, c.name FROM memory_entry_concepts ec "
            "JOIN memory_concepts c ON c.concept_id = ec.concept_id "
            "WHERE ec.entry_id=? ORDER BY c.level DESC LIMIT 1", (r["entry_id"],)).fetchone()
        if c:
            truth[r["entry_id"]] = (c["concept_id"], c["name"])
    keep = [r for r in rows if r["entry_id"] in truth]
    return keep, truth


def concept_eval(keep, truth, encode, label):
    """留一法：最近质心，看能不能落回自己的概念。"""
    vecs = np.vstack([encode(r["l1_summary"]) for r in keep])
    members: dict[str, list[int]] = {}
    for i, r in enumerate(keep):
        members.setdefault(truth[r["entry_id"]][0], []).append(i)

    ok, margins = 0, []
    for i, r in enumerate(keep):
        scored = []
        for cid, idxs in members.items():
            pool = [j for j in idxs if j != i]
            if pool:
                scored.append((cosine(vecs[i], centroid(vecs[pool])), cid))
        if not scored:
            continue
        scored.sort(reverse=True)
        best = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        if best[1] == truth[r["entry_id"]][0]:
            ok += 1
        margins.append((best[0] - second, best[1] == truth[r["entry_id"]][0]))

    acc = ok / len(keep)
    margins.sort(reverse=True)
    head = margins[:max(1, int(len(margins) * 0.2))]
    print(f"  {label:<16} accuracy@1 = {acc:.0%}   "
          f"（高 margin 前 20% 准确率 {sum(1 for _, o in head if o) / len(head):.0%}，"
          f"余弦范围 {margins[-1][0]:.3f}~{margins[0][0]:.3f}）")
    return acc


def pair_eval(keep, encode, label, threshold=0.0):
    """对每条"改动型"记忆，看它最近的前任是不是"决定/改动"型。"""
    acts = {r["entry_id"]: tb.speech_act(r["l1_summary"]) for r in keep}
    vecs = {r["entry_id"]: encode(r["l1_summary"]) for r in keep}
    order = {r["entry_id"]: i for i, r in enumerate(keep)}     # 入库顺序 ≈ 原文顺序
    changes = [r for r in keep if acts[r["entry_id"]] == "change"]
    good, total = 0, 0
    detail = []
    for b in changes:
        # 只看比它早的：前任必须在前，否则就成"未来影响过去"
        cands = [(cosine(vecs[b["entry_id"]], vecs[a["entry_id"]]), a)
                 for a in keep
                 if order[a["entry_id"]] < order[b["entry_id"]]
                 and acts[a["entry_id"]] in ("change", "decision")]
        if not cands:
            continue
        cands.sort(key=lambda x: -x[0])
        s, best = cands[0]
        if s < threshold:
            continue
        total += 1
        ok = acts[best["entry_id"]] == "decision"
        good += ok
        detail.append((b["l1_summary"][:22], best["l1_summary"][:22], round(s, 3), ok))
    if total:
        print(f"  {label:<16} 改动型 {total} 条，前任是「决定」的 {good} 条 = {good / total:.0%}")
        for d in detail:
            print(f"      {'✓' if d[3] else '✗'} {d[2]:.3f}  {d[0]} ← {d[1]}")
    else:
        print(f"  {label:<16} 没有可评的改动型记忆")


def main():
    conn = tb.connect()
    keep, truth = load(conn)
    print(f"样本 {len(keep)} 条 / {len({v[0] for v in truth.values()})} 个概念\n")

    print("【一】概念挂靠（留一法，最近质心）")
    concept_eval(keep, truth, _bigram_vec, "bigram 基线")
    vs = VectorSpace(dim=48).fit([r["l1_summary"] for r in keep])
    concept_eval(keep, truth, vs.encode, "LSA 向量")

    print("\n【二】冲突配对（改动型记忆找前任）")
    pair_eval(keep, _bigram_vec, "bigram 基线")
    pair_eval(keep, vs.encode, "LSA 向量")

    conn.close()


_SPACE = None


def _bigram_vec(text: str) -> np.ndarray:
    """基线：纯字面 bigram 向量（无降维）。用全局词表对齐。"""
    global _SPACE
    if _SPACE is None:
        conn = tb.connect()
        docs = [r["l1_summary"] for r in conn.execute(
            "SELECT l1_summary FROM memory_entries")]
        conn.close()
        vocab = sorted({t for d in docs for t in tb.tokenize(d)})
        _SPACE = {t: i for i, t in enumerate(vocab)}
    v = np.zeros(len(_SPACE))
    ts = tb.tokenize(text)
    for t in ts:
        j = _SPACE.get(t)
        if j is not None:
            v[j] = 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


if __name__ == "__main__":
    main()
