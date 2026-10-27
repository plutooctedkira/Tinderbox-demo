"""诊断：规则提炼的分数分布，以及"按文档预算 + 绝对阈值"能压到多少。"""
import sys
from pathlib import Path

sys.path.insert(0, r"E:\记忆库\demo")
import tb  # noqa: E402

CORPUS = Path(r"E:\记忆库\demo\corpus\clean")
DEMO = Path(r"E:\记忆库\demo\sample.txt")


def items_of(text: str):
    out = []
    for start, end in tb.split_semantic(text):
        for it in tb.extract(text, text[start:end], chunk_start=start):
            out.append(it)
    return out


def score_of(it: dict) -> float:
    """复刻 extract 内部的打分，用于排序（不改原函数）。"""
    para = it["l1_summary"]
    s = 0.0
    for name, kws in tb.CATEGORY_RULES:
        if any(k in para for k in kws):
            s += 3
            break
    s += sum(1 for k in ("我们", "所以", "因为", "但是", "如果") if k in para)
    s += min(len(para), 140) / 140.0
    if any(ch.isdigit() for ch in para):
        s += 1.0
    return s


def report(name: str, text: str):
    items = items_of(text)
    scored = sorted((score_of(i) for i in items), reverse=True)
    n = len(scored)
    print(f"\n【{name}】{len(text)} 字 → {len(tb.split_semantic(text))} 块 → {n} 条")
    if not scored:
        return
    import statistics
    print(f"  分数：最高 {scored[0]:.1f} 中位 {statistics.median(scored):.1f} 最低 {scored[-1]:.1f}")
    budget = max(3, min(60, len(text) // 400))
    print(f"  按字数预算（{budget} 条）直接截断 → 保留 {min(budget, n)} 条")
    for t in (2.0, 2.5, 3.0, 3.5):
        keep = sum(1 for s in scored if s >= t)
        print(f"  阈值 {t:.1f} → 保留 {keep} 条（{keep / n:.0%}）")


report("小说《孔乙己》", (CORPUS / "孔乙己.txt").read_text(encoding="utf-8"))
report("小说《藥》", (CORPUS / "藥.txt").read_text(encoding="utf-8"))
report("demo sample.txt", DEMO.read_text(encoding="utf-8"))
