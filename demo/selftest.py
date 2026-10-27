"""不变量自测：跑完 demo 后执行，验证数据模型没有被悄悄破坏。

跑法：python demo/selftest.py
返回码：0 全过；1 有失败项（可直接接进 CI）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402

CHECKS: list[tuple[str, callable]] = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


@check("user_id 取值唯一（单用户模式）")
def _(conn):
    vals = [r[0] for r in conn.execute("SELECT DISTINCT user_id FROM memory_entries")]
    return len(vals) <= 1, f"取值 {vals}"


# ---------------------------------------------------------------- 版本链
@check("每个版本组只有一个 active")
def _(conn):
    bad = conn.execute(
        "SELECT memory_group_id, count(*) c FROM memory_entries "
        "WHERE status='active' GROUP BY memory_group_id HAVING c > 1").fetchall()
    return len(bad) == 0, f"{len(bad)} 个组有多个 active" if bad else "ok"


@check("组内版本号从 1 连续排到 N")
def _(conn):
    bad = []
    for g in conn.execute("SELECT DISTINCT memory_group_id FROM memory_entries"):
        vs = [r[0] for r in conn.execute(
            "SELECT version_no FROM memory_entries WHERE memory_group_id=? ORDER BY 1",
            (g[0],))]
        if vs != list(range(1, len(vs) + 1)):
            bad.append((g[0], vs))
    return not bad, f"{len(bad)} 组版本号断档" if bad else "ok"


@check("superseded 必须指向同组更高版本")
def _(conn):
    bad = conn.execute(
        "SELECT e.entry_id FROM memory_entries e LEFT JOIN memory_entries n "
        "  ON n.entry_id = e.superseded_by "
        "WHERE e.status='superseded' AND (n.entry_id IS NULL "
        "  OR n.memory_group_id <> e.memory_group_id OR n.version_no <= e.version_no)"
    ).fetchall()
    return len(bad) == 0, f"{len(bad)} 条指针不对" if bad else "ok"


# ---------------------------------------------------------------- 索引
@check("FTS 索引条目数与状态分布一致")
def _(conn):
    st = tb.stats(conn)
    live = st["active"] + st["pending_merge"]
    ok = st["fts_active"] == live and st["fts_history"] == st["archived"] + st["superseded"]
    return ok, f"active {st['fts_active']}/{live} · history {st['fts_history']}/{st['archived'] + st['superseded']}"


# ---------------------------------------------------------------- 冲突
@check("未裁决的冲突，其新条目必须是 pending_merge")
def _(conn):
    bad = conn.execute(
        "SELECT c.conflict_id FROM memory_conflicts c "
        "JOIN memory_entries e ON e.entry_id = c.new_entry_id "
        "WHERE c.state='open' AND e.status <> 'pending_merge'").fetchall()
    return len(bad) == 0, f"{len(bad)} 处状态不符" if bad else "ok"


# ---------------------------------------------------------------- 关系
@check("关系表两端都真实存在")
def _(conn):
    bad = conn.execute(
        "SELECT r.relation_id FROM memory_relations r "
        "LEFT JOIN memory_entries a ON a.entry_id = r.from_entry "
        "LEFT JOIN memory_entries b ON b.entry_id = r.to_entry "
        "WHERE a.entry_id IS NULL OR b.entry_id IS NULL").fetchall()
    return len(bad) == 0, f"{len(bad)} 条悬空" if bad else "ok"


# ---------------------------------------------------------------- 概念
@check("概念树无环")
def _(conn):
    parent = {r["concept_id"]: r["parent_id"] for r in conn.execute(
        "SELECT concept_id, parent_id FROM memory_concepts")}
    bad = 0
    for cid in parent:
        seen, cur = set(), cid
        while cur:
            if cur in seen:
                bad += 1
                break
            seen.add(cur)
            cur = parent.get(cur)
    return bad == 0, f"{bad} 个概念成环" if bad else "ok"


@check("概念层级与父子关系一致")
def _(conn):
    bad = conn.execute(
        "SELECT c.concept_id, c.level, p.level pl FROM memory_concepts c "
        "JOIN memory_concepts p ON p.concept_id = c.parent_id "
        "WHERE c.level <> p.level + 1").fetchall()
    return len(bad) == 0, f"{len(bad)} 个层级不匹配：{[r[0] for r in bad][:3]}" if bad else "ok"


# ---------------------------------------------------------------- L0
@check("每条记忆的 L0 区间都落在材料范围内")
def _(conn):
    bad = []
    for r in conn.execute(
            "SELECT e.entry_id, e.l0_offset, e.l0_length, d.char_count "
            "FROM memory_entries e JOIN memory_documents d ON d.doc_id = e.doc_id"):
        if r["l0_offset"] < 0 or r["l0_offset"] + r["l0_length"] > r["char_count"]:
            bad.append(r["entry_id"])
    return not bad, f"{len(bad)} 条越界" if bad else "ok"


# ---------------------------------------------------------------- 检索
@check("检索分数各分量都在 0~1")
def _(conn):
    for q in ("选址", "豆子", "连廊"):
        for h in tb.search(conn, q, top_k=5):
            for k in ("s_rel", "s_rec", "weight"):
                if not (0.0 <= h[k] <= 1.0):
                    return False, f"「{q}」的 {k}={h[k]}"
    return True, "ok"


@check("hybrid 模式下同一版本组只出现一次")
def _(conn):
    for q in ("选址", "大学城", "豆子"):
        hits = tb.search(conn, q, mode="hybrid", top_k=10)
        groups = [h.get("group") or h["entry_id"] for h in hits]
        if len(groups) != len(set(groups)):
            return False, f"「{q}」有重复组"
    return True, "ok"


def main():
    conn = tb.connect()
    width = max(len(n) for n, _ in CHECKS) + 2
    fails = 0
    for name, fn in CHECKS:
        try:
            ok, detail = fn(conn)
        except Exception as e:                       # 断言内部报错也算失败
            ok, detail = False, f"{type(e).__name__}: {e}"
        fails += 0 if ok else 1
        print(f"  {'✓' if ok else '✗'} {name:<{width}}{detail}")
    conn.close()
    print(f"\n{len(CHECKS) - fails}/{len(CHECKS)} 项通过")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
