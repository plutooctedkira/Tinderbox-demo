"""验浮现面板：接口有数据、页面有容器、去重生效、点击能打开详情。"""
import json
import time
import urllib.request

time.sleep(2)
BASE = "http://127.0.0.1:8777"
TOKEN = [ln.split("=", 1)[1].strip()
         for ln in open(r"E:\记忆库\demo\.env", encoding="utf-8")
         if ln.startswith("API_TOKEN=")][0]
H = {"Authorization": f"Bearer {TOKEN}"}


def get(path):
    r = urllib.request.Request(BASE + path, headers=H)
    with urllib.request.urlopen(r, timeout=8) as resp:
        return json.loads(resp.read().decode())


ctx = get("/api/context?k=4")
print(f"① /api/context → {len(ctx['memories'])} 条 · 待裁决 {ctx['pending_conflicts']}"
      f" · 未精修 {ctx['provisional']}")
for m in ctx["memories"]:
    print(f"   {m['score']:.2f}  {m['l1_summary'][:36]}")
    print(f"        └ {m['why']}")

topics = [(m["keywords"] or "").split()[0] if m["keywords"] else "" for m in ctx["memories"]]
print(f"\n② 去重：话题 = {topics} → {'无重复 ✓' if len(set(topics)) == len(topics) else '有重复 ✗'}")

page = urllib.request.Request(BASE + "/", headers=H)
with urllib.request.urlopen(page, timeout=8) as r:
    html = r.read().decode()
print(f"\n③ 页面：{len(html)} 字节 · 含容器 {'Yes' if 'id=\"ctx\"' in html else 'No'}"
      f" · 含渲染函数 {'Yes' if 'renderContext' in html else 'No'}"
      f" · 含样式 {'Yes' if '.ctxrow' in html else 'No'}")

# 点进去的入口：/api/entry 能拿到详情
eid = ctx["memories"][0]["entry_id"]
detail = get("/api/entry?id=" + eid)
print(f"\n④ 点开第一条 → 状态 {detail['status']} · 原文片段 {len(detail.get('text', ''))} 字")
