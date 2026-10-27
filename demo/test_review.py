"""端到端验证：从接口取待裁决 → POST 裁决 → 确认版本链与状态。"""
import json
import time
import urllib.request

time.sleep(2)
BASE = "http://127.0.0.1:8777"


def get(p):
    with urllib.request.urlopen(BASE + p, timeout=8) as r:
        return json.loads(r.read().decode())


def post(p, body):
    req = urllib.request.Request(
        BASE + p, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


d = get("/api/conflicts")
print(f"待裁决 {len(d['items'])} 处")
for c in d["items"]:
    print(f"  [{c['relation']} {c['confidence']:.2f}] {c['reason'][:40]}")
    print(f"     旧：{(c['old'] or {}).get('l1_summary', '')[:38]}")
    print(f"     新：{(c['new'] or {}).get('l1_summary', '')[:38]}")

if not d["items"]:
    print("没有待裁决的，先跑 run_complement 造一条")
    raise SystemExit(0)

target = d["items"][0]
new_id = target["new"]["entry_id"]
before = get("/api/entry?id=" + new_id)
print(f"\n裁决前：新条目状态 = {before['status']}")

out = post("/api/conflicts/resolve", {"conflict_id": target["conflict_id"],
                                      "resolution": "supersede"})
print("裁决返回：", json.dumps(out, ensure_ascii=False)[:120])

after = get("/api/entry?id=" + new_id)
print(f"裁决后：状态 = {after['status']}  版本 = v{after['version_no']}")
print("版本链：")
for n in after["chain"]:
    print(f"  {'●' if n['status'] == 'active' else '○'} v{n['version_no']} {n['status']:<11} {n['l1_summary'][:32]}")

rest = get("/api/conflicts")
print(f"\n剩余待裁决 {len(rest['items'])} 处")
