"""测试：新增补充记忆，原有记忆一个字都不能动。

跑法：python demo/run_complement.py   （需先跑过 run_demo.py）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tb  # noqa: E402
from demo_util import Tee, rule  # noqa: E402

BASE = Path(__file__).resolve().parent


def snapshot(conn) -> dict:
    """原有记忆的快照：状态、版本、摘要，用来证明"一条都没动"。"""
    return {r["entry_id"]: (r["status"], r["version_no"], r["l1_summary"],
                            r["superseded_by"])
            for r in conn.execute(
                "SELECT entry_id, status, version_no, l1_summary, superseded_by "
                "FROM memory_entries")}


def main():
    logf = open(BASE / "out" / "complement.log", "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, logf)

    conn = tb.init_db()   # 只补建缺失的表，不重置数据
    before = snapshot(conn)
    base_conf = len(tb.list_conflicts(conn))
    st0 = tb.stats(conn)
    rule("基线")
    print(f"  原有 {st0['entries']} 条 / {st0['documents']} 份材料")
    print(f"  冲突 {base_conf} 处待裁决")

    rule("灌入补充材料（只加信息，不改结论）")
    text = (BASE / "sample3.txt").read_text(encoding="utf-8")
    res = tb.ingest(conn, text, title="咖啡车补充记录")
    print(f"  新增 {len(res['entries'])} 条 L1")
    for e in res["entries"]:
        print(f"    [{e['category']:<10}] {e['l1_summary'][:40]}")

    # 新材料属于同一个项目：把它的根概念挂到已有根概念下（否则每份补充材料都会另起一列）
    tree = tb.concept_tree(conn)
    kids: dict = {}
    for x in tree:
        kids.setdefault(x["parent_id"], []).append(x)

    def rollup(c):
        return c["direct"] + sum(rollup(k) for k in kids.get(c["concept_id"], []))

    roots = [x for x in tree if x["parent_id"] is None]
    if len(roots) > 1:
        keep = max(roots, key=rollup)
        with tb.tx(conn):
            for r in roots:
                if r["concept_id"] != keep["concept_id"]:
                    conn.execute(
                        "UPDATE memory_concepts SET parent_id=?, level=1 WHERE concept_id=?",
                        (keep["concept_id"], r["concept_id"]))
        others = [r["name"] for r in roots if r["concept_id"] != keep["concept_id"]]
        tb.relevel(conn)
        print(f"  ↳ 新材料主题「{'、'.join(others)}」已并入已有项目「{keep['name']}」")

    rule("验证一：原有记忆有没有被动过")
    after = snapshot(conn)
    changed = [k for k in before if after.get(k) != before[k]]
    print(f"  原有 {len(before)} 条，内容/状态/版本发生变化的有：{len(changed)} 条")
    if changed:
        for k in changed[:5]:
            print(f"    ✗ {k}\n      前 {before[k][:2]}\n      后 {after[k][:2]}")
    else:
        print("  ✓ 零改动：没有一条被作废、被改摘要、被抬版本号")

    rule("验证二：有没有误判成冲突")
    new_conf = tb.list_conflicts(conn)
    print(f"  当前待裁决冲突：{len(new_conf)} 处（灌入前 {base_conf} 处）")
    if len(new_conf) > base_conf:
        print("  ✗ 新增了冲突，说明补充被误判成覆盖")
    else:
        print("  ✓ 没有新增冲突：补充材料没有被当成'改口'")

    rule("验证三：有没有认出'这是补充关系'")
    comps = res.get("complements", [])
    print(f"  识别出 {len(comps)} 组互补关系：")
    for c in comps:
        print(f"    {c['confidence']:.2f}  新：{c['new_summary'][:30]}")
        print(f"          旧：{c['old_summary'][:30]}")
        print(f"          理由：{c['reason']}")

    rule("验证四：新记忆能不能和旧的一起被检索到")
    for q in ("连廊", "耶加", "杯盖", "太阳能"):
        hits = tb.search(conn, q)
        print(f"  查「{q}」→ {len(hits)} 条" + (f"：{hits[0]['l1_summary'][:34]}" if hits else ""))

    rule("汇总")
    st1 = tb.stats(conn)
    print(f"  条目 {st0['entries']} → {st1['entries']}（+{st1['entries'] - st0['entries']}）")
    print(f"  材料 {st0['documents']} → {st1['documents']}")
    print(f"  版本链 {len(tb.list_chains(conn))} 组（应保持不变）")
    print(f"  冲突 {len(new_conf)} 处 · 互补关系 {len(comps)} 组")
    print(f"  L0 {st0['l0_bytes']:,} → {st1['l0_bytes']:,} 字节")

    conn.close()
    logf.close()
    sys.stdout = sys.__stdout__


if __name__ == "__main__":
    main()
