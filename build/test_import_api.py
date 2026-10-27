"""验面板导入：试跑不写库、真跑入库、项目名生效。"""
import json
import urllib.error
import urllib.request
from pathlib import Path

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
tok = Path(r"E:\记忆库\.imp\token.txt").read_text(encoding="utf-8").strip()
H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
BASE = "http://127.0.0.1:8814"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST", headers=H)
    try:
        with op.open(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


SEED = str(Path(r"E:\记忆库\demo\seed_notes"))

print("① 不存在的路径")
print("  ", post("/api/import", {"path": "D:\\no-such-dir-xyz"})[0])

print("\n② 试跑")
code, body = post("/api/import", {"path": SEED, "dry_run": True})
print("  ", code, body.get("stats"), "项目:", body.get("project"))

print("\n③ 真跑")
code, body = post("/api/import", {"path": SEED, "project": "咖啡车生意"})
print("  ", code, body.get("stats"), "项目:", body.get("project"))
print("   问题：", body.get("failures"))

print("\n④ 再跑一次（应全跳过）")
code, body = post("/api/import", {"path": SEED, "project": "咖啡车生意"})
print("  ", code, body.get("stats"))

print("\n⑤ 概念树")
items = json.load(op.open(urllib.request.Request(BASE + "/api/concepts", headers=H), timeout=10))["items"]
roots = [x for x in items if x["parent_id"] is None]
print("   根概念:", [(r["name"], r["direct"]) for r in roots])
print("   子项数:", sum(1 for x in items if x["parent_id"]))
