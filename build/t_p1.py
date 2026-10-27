"""验 P1：分类筛选数据、历史版本、回滚、备份接口。"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = 8820
BASE = f"http://127.0.0.1:{PORT}"
DATA = Path(r"E:\记忆库\.p1")
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
tok = (DATA / "token.txt").read_text(encoding="utf-8").strip()
H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}


def get(p):
    return json.load(op.open(urllib.request.Request(BASE + p, headers=H), timeout=10))


def post(p, b):
    req = urllib.request.Request(BASE + p, data=json.dumps(b).encode(), method="POST", headers=H)
    try:
        with op.open(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# 导入一些数据
st, j = post("/api/import", {"path": str(Path(r"E:\记忆库\demo\seed_notes")), "project": "测试"})
jid = j["job"]
for _ in range(100):
    time.sleep(0.3)
    job = get("/api/import/status?id=" + jid)["job"]
    if job["state"] != "running":
        break
print("导入：", job["state"], job["entries"], "条")

eid = get("/api/search?q=%E5%AE%9A%E4%BB%B7")["items"][0]["entry_id"]

print("\n① 改两次 → 历史版本应有 2 条")
post("/api/entry/update", {"entry_id": eid, "summary": "美式 15，拿铁 21，手冲 25"})
post("/api/entry/update", {"entry_id": eid, "summary": "美式 15，拿铁 22，手冲 25"})
d = get("/api/entry?id=" + eid)
print("   历史版本:", len(d["revisions"]))
for r in d["revisions"]:
    print("   ", r["at"][11:19], r["old"][:30])

print("\n② 回滚到最早那版")
rev = d["revisions"][-1]["revision_id"]
print("  ", post("/api/entry/revert", {"entry_id": eid, "revision_id": rev}))
d2 = get("/api/entry?id=" + eid)
print("   现在摘要:", d2["l1_summary"][:40])
print("   历史版本:", len(d2["revisions"]), "条（回滚也留痕）")

print("\n③ 分类筛选数据")
for cat in ("decision", "knowledge", "task"):
    items = get(f"/api/list?status=active&category={cat}&limit=5")["items"]
    print(f"   {cat}: {len(items)} 条")

print("\n④ 备份")
st, b = post("/api/backup", {"keep": 3})
print("  ", st, b.get("result", {}).get("counts"), "校验", b.get("result", {}).get("ok"))
