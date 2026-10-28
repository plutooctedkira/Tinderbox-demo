"""验新搜索接口：分页 / 筛选 / 排序 / 来源 / 片段。"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8839"
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
tok = Path(r"E:\记忆库\.vault\token.txt").read_text(encoding="utf-8").strip()
H = {"Authorization": "Bearer " + tok}


def g(path):
    return json.load(op.open(urllib.request.Request(BASE + path, headers=H), timeout=20))


q = urllib.parse.quote("定价")
print("① 默认（相关性）")
d = g(f"/api/search?q={q}")
print(f"   total={d['total']} · 返回 {len(d['items'])} · {d['ms']}ms")
for it in d["items"][:3]:
    print(f"   {it['s_rel']:.2f} {it['status']:<12}{it['origin']['doc_title'][:14]:<16}{it['snippet'][:34]}")

print("\n② 按时间排序 + 分页 limit=2 offset=2")
d2 = g(f"/api/search?q={q}&sort=time&limit=2&offset=2")
print(f"   total={d2['total']} · 本页 {len(d2['items'])}")
for it in d2["items"]:
    print("   ", it["created_at"][:10], it["l1_summary"][:30])

print("\n③ 类型筛选 decision")
d3 = g(f"/api/search?q={q}&category=decision")
print(f"   total={d3['total']} �� 全为 decision:", all(i["category"] == "decision" for i in d3["items"]))

print("\n④ 状态筛选 active")
d4 = g(f"/api/search?q={q}&status=active")
print(f"   total={d4['total']} · 全为 active:", all(i["status"] == "active" for i in d4["items"]))

print("\n⑤ 片段高亮")
snip = [i["snippet"] for i in d["items"] if i["snippet"]]
print("   有片段:", len(snip), "条；示例:", snip[0][:60] if snip else "无")
print("   含 <mark>:", any("<mark>" in x for x in snip))
