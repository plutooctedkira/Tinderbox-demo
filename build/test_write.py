"""端到端测写接口：新增 → 改 → 归档 → 搜索验证。"""
import json
import urllib.error
import urllib.request
from pathlib import Path

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
tok = Path(r"E:\记忆库\.vault\token.txt").read_text(encoding="utf-8").strip()
H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
BASE = "http://127.0.0.1:8804"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST", headers=H)
    try:
        with op.open(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


print("① 缺依据 → 应 422")
print("  ", post("/api/add", {"summary": "决定把营业时间提前到 10 点"})[0])

print("\n② 结论太短 → 应 422")
print("  ", post("/api/add", {"summary": "定了", "reason": "因为要赶早高峰的客流"})[0])

print("\n③ 正常新增 → 201/200")
code, body = post("/api/add", {
    "summary": "决定把营业时间提前到 10 点",
    "reason": "园区早会一般在 9 点半散场，散场后十分钟是第一个高峰",
    "category": "decision",
})
print("  ", code, body.get("result", {}).get("summary", body)[:50] if code == 200 else body)
eid = body.get("result", {}).get("entry_id")

print("\n④ 搜得到吗（新词「早会」）")
req = urllib.request.Request(BASE + "/api/search?q=%E6%97%A9%E4%BC%9A", headers={"Authorization": "Bearer " + tok})
d = json.load(op.open(req, timeout=8))
print("  ", len(d.get("items", [])), "条")

print("\n⑤ 改摘要")
print("  ", post("/api/entry/update", {"entry_id": eid,
                                       "summary": "决定把营业时间提前到 09:50"}))
print("   再搜「09:50」:", end=" ")
req = urllib.request.Request(BASE + "/api/search?q=09%3A50", headers={"Authorization": "Bearer " + tok})
print(len(json.load(op.open(req, timeout=8)).get("items", [])), "条")

print("\n⑥ 归档")
print("  ", post("/api/entry/archive", {"entry_id": eid, "archived": True}))
req = urllib.request.Request(BASE + "/api/search?q=09%3A50", headers={"Authorization": "Bearer " + tok})
print("   归档后现行搜索:", len(json.load(op.open(req, timeout=8)).get("items", [])), "条（应为 0）")

print("\n⑦ 恢复")
print("  ", post("/api/entry/archive", {"entry_id": eid, "archived": False}))

print("\n⑧ 没有的条目 → 404")
print("  ", post("/api/entry/update", {"entry_id": "mem-nope", "summary": "随便改改看"})[0])

