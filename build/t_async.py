"""验异步导入（port 参数化）。"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8819
BASE = f"http://127.0.0.1:{PORT}"
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
tok = Path(r"E:\记忆库\.imp2\token.txt").read_text(encoding="utf-8").strip()
H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}


def post(p, body):
    req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(), method="POST", headers=H)
    try:
        with op.open(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get(p):
    return json.load(op.open(urllib.request.Request(BASE + p, headers=H), timeout=10))


def wait(job_id, timeout=180):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        j = get("/api/import/status?id=" + job_id)["job"]
        if j != last:
            print(f"   {j['state']:<8}{j['done']}/{j['total']}  新增 {j['added']} · {j['entries']} 条")
            last = j
        if j["state"] != "running":
            return j
        time.sleep(0.4)
    return None


SEED = str(Path(r"E:\记忆库\demo\seed_notes"))

print("① 试跑")
st, body = post("/api/import", {"path": SEED, "dry_run": True})
print("   启动:", st, body)
wait(body["job"])

print("\n② 真跑")
st, body = post("/api/import", {"path": SEED, "project": "咖啡车生意"})
j = wait(body["job"])
print("   最终:", {k: j[k] for k in ("state", "total", "added", "skipped", "failed", "entries")})

print("\n③ 再跑（幂等）")
st, body = post("/api/import", {"path": SEED, "project": "咖啡车生意"})
j = wait(body["job"])
print("   最终:", {k: j[k] for k in ("state", "added", "skipped", "entries")})

print("\n④ meta:", get("/api/meta"))
print("⑤ 坏路径:", post("/api/import", {"path": "D:\\no-such"})[0])
