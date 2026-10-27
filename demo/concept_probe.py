"""概念挂靠阈值探针：用现有 30 条数据，看看"多少分才算同一概念"。

没有嵌入模型，用 bigram TF-IDF 做替身——它验证不了语义泛化，但能验证
**阈值的行为**：取多少会导致概念爆炸，取多少会导致张冠李戴。

跑法：python demo/concept_probe.py
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402


def build_vocab(docs: list[str]) -> list[str]:
    vocab = set()
    for d in docs:
        vocab.update(tb.tokenize(d))
    return sorted(vocab)


def tfidf(docs: list[str]) -> list[dict[str, float]]:
    vocab = build_vocab(docs)
    idx = {t: i for i, t in enumerate(vocab)}
    df = Counter()
    for d in docs:
        for t in set(tb.tokenize(d)):
            df[t] += 1
    n = len(docs)
    out = []
    for d in docs:
        toks = tb.tokenize(d)
        tf = Counter(toks)
        vec = {}
        for t, c in tf.items():
            w = (c / max(len(toks), 1)) * (math.log((1 + n) / (1 + df[t])) + 1.0)
            vec[idx[t]] = w
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        out.append({k: v / norm for k, v in vec.items()})
    return out


def cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def centroid(vecs: list[dict]) -> dict:
    acc: dict[int, float] = defaultdict(float)
    for v in vecs:
        for k, x in v.items():
            acc[k] += x
    norm = math.sqrt(sum(x * x for x in acc.values())) or 1.0
    return {k: x / norm for k, x in acc.items()}


def main():
    conn = tb.connect()
    rows = conn.execute(
        "SELECT e.entry_id, e.l1_summary FROM memory_entries e "
        "WHERE e.status IN ('active','pending_merge') ORDER BY e.row_id").fetchall()
    # 真值：条目所属的"小节"概念（层级最深的那个）
    truth = {}
    for r in rows:
        cons = [x[0] for x in conn.execute(
            "SELECT c.concept_id FROM memory_entry_concepts ec "
            "JOIN memory_concepts c ON c.concept_id = ec.concept_id "
            "WHERE ec.entry_id = ? ORDER BY c.level DESC LIMIT 1", (r["entry_id"],))]
        if cons:
            truth[r["entry_id"]] = cons[0]

    names = {c["concept_id"]: c["name"] for c in conn.execute(
        "SELECT concept_id, name FROM memory_concepts")}

    entries = [(r["entry_id"], r["l1_summary"]) for r in rows if r["entry_id"] in truth]
    vecs = tfidf([s for _, s in entries])
    members: dict[str, list[int]] = defaultdict(list)
    for i, (eid, _) in enumerate(entries):
        members[truth[eid]].append(i)

    print(f"样本：{len(entries)} 条记忆 / {len(members)} 个概念")
    print(f"分词：{tb.TOKENIZER}（bigram 替身，无语义泛化）\n")

    # 留一法：拿条目去比"不含自己"的概念质心
    results = []       # (真值概念, 预测概念, 最高余弦, 是否正确)
    for i, (eid, _) in enumerate(entries):
        best_c, best_s = None, -1.0
        for cid, idxs in members.items():
            pool = [j for j in idxs if j != i]
            if not pool:
                continue
            s = cosine(vecs[i], centroid([vecs[j] for j in pool]))
            if s > best_s:
                best_c, best_s = cid, s
        if best_c is None:
            continue
        results.append((truth[eid], best_c, best_s, best_c == truth[eid]))

    ok = sum(1 for r in results if r[3])
    print(f"accuracy@1（最近质心）：{ok}/{len(results)} = {ok / len(results):.0%}")

    right = [r[2] for r in results if r[3]]
    wrong = [r[2] for r in results if not r[3]]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else float("nan")
    print(f"命中时余弦：最低 {min(right):.3f} / 中位 {med(right):.3f} / 最高 {max(right):.3f}")
    if wrong:
        print(f"错配时余弦：最低 {min(wrong):.3f} / 中位 {med(wrong):.3f} / 最高 {max(wrong):.3f}")

    # ---- 用"与第二名的差距"当置信度，比绝对分数可靠 ----
    scored = []
    for i, (eid, _) in enumerate(entries):
        pairs = []
        for cid, idxs in members.items():
            pool = [j for j in idxs if j != i]
            if pool:
                pairs.append((cosine(vecs[i], centroid([vecs[j] for j in pool])), cid))
        if not pairs:
            continue
        pairs.sort(reverse=True)
        best_s, best_c = pairs[0]
        second = pairs[1][0] if len(pairs) > 1 else 0.0
        scored.append({"eid": eid, "best": best_s, "second": second,
                       "margin": best_s - second, "ok": best_c == truth[eid],
                       "pred": best_c, "true": truth[eid]})

    print("\n置信度用「与第二名的差距」（margin），而不是绝对余弦")
    print("  高 margin 的前 N 条里，挂靠准确率如何：")
    ranked = sorted(scored, key=lambda r: -r["margin"])
    for frac in (0.1, 0.2, 0.3, 0.5, 1.0):
        k = max(1, int(len(ranked) * frac))
        head = ranked[:k]
        acc = sum(1 for r in head if r["ok"]) / k
        print(f"    前 {frac:>4.0%}（{k:>2} 条，margin ≥ {head[-1]['margin']:.3f}）  "
              f"准确率 {acc:.0%}")

    print("\n若要求准确率 ≥ 90%，最多能自动挂靠几条：")
    found = False
    for k in range(len(ranked), 0, -1):
        head = ranked[:k]
        acc = sum(1 for r in head if r["ok"]) / k
        if acc >= 0.9:
            print(f"    取前 {k} 条（margin ≥ {head[-1]['margin']:.3f}）：准确率 {acc:.0%}，"
                  f"覆盖率 {k / len(ranked):.0%}")
            found = True
            break
    if not found:
        print(f"    做不到——即使取 margin 最高的 1 条也只有 "
              f"{'错' if not ranked[0]['ok'] else '对'}，全量准确率 "
              f"{sum(1 for r in ranked if r['ok']) / len(ranked):.0%}")

    print("\n如果阈值取在 margin 的分位数上，会新建多少概念：")
    for frac in (0.25, 0.5, 0.75):
        cut = sorted(r["margin"] for r in ranked)[int(len(ranked) * frac) - 1]
        auto = [r for r in ranked if r["margin"] >= cut]
        hit = sum(1 for r in auto if r["ok"])
        print(f"    闸门取 {frac:.0%} 分位（margin ≥ {cut:.3f}）：自动挂靠 {len(auto)} 条"
              f"（准确 {hit / len(auto):.0%}），其余 {len(ranked) - len(auto)} 条进待归类")

    # 概念之间的相似度：哪些小节其实是一回事
    cents = {cid: centroid([vecs[j] for j in idxs]) for cid, idxs in members.items()}
    pairs = []
    ids = list(cents)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            pairs.append((cosine(cents[ids[a]], cents[ids[b]]),
                          names.get(ids[a], "?"), names.get(ids[b], "?")))
    pairs.sort(reverse=True)
    print("\n概念两两相似度 top5（越高越像'同一件事'）：")
    for s, x, y in pairs[:5]:
        print(f"  {s:.3f}  {x} ↔ {y}")
    conn.close()


if __name__ == "__main__":
    main()
