"""验鉴权：无令牌 401、错令牌计数、正确令牌放行、登录 cookie、限流、无 CORS。"""
import json
import time
import urllib.error
import urllib.request



# 自己起一个服务，别依赖外部进程（原来的写法要求事先有个 server 在 8777 上跑）
import atexit
import socket
import subprocess
import sys
from pathlib import Path

_DEMO = Path(__file__).resolve().parent
_proc = subprocess.Popen([sys.executable, str(_DEMO / "web.py")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
atexit.register(lambda: _proc.terminate())
for _ in range(120):
    try:
        socket.create_connection(("127.0.0.1", 8777), timeout=0.5).close()
        break
    except OSError:
        time.sleep(0.1)

BASE = "http://127.0.0.1:8777"
TOKEN = [ln.split("=", 1)[1].strip()
         for ln in open(r"E:\记忆库\demo\.env", encoding="utf-8")
         if ln.startswith("API_TOKEN=")][0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OP = urllib.request.build_opener(NoRedirect)


def req(path, token=None, cookie=None, method="GET", data=None, form=False):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cookie:
        headers["Cookie"] = cookie
    body = None
    if data is not None:
        if form:
            body = "&".join(f"{k}={v}" for k, v in data.items()).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with OP.open(r, timeout=8) as resp:
            return resp.status, resp.read()[:200], dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200], dict(e.headers)


print("① 无令牌")
code, body, _ = req("/api/search?q=%E9%80%89%E5%9D%80")
print(f"  {code}  {body.decode('utf-8', 'ignore')[:60]}")

print("\n② 错令牌")
code, body, _ = req("/api/search?q=x", token="wrong-token")
print(f"  {code}  {body.decode('utf-8', 'ignore')[:60]}")

print("\n③ 正确令牌 + 安全头")
code, body, hdr = req("/api/search?q=%E9%80%89%E5%9D%80", token=TOKEN)
sec = [k for k in hdr if k.lower() in ("x-content-type-options", "referrer-policy", "x-frame-options")]
print(f"  {code}  {len(body)} 字节  安全头 {sec}")

print("\n④ 未登录访问首页")
code, body, hdr = req("/")
print(f"  {code}  Location={hdr.get('Location')}")

print("\n⑤ 登录页开放")
code, body, _ = req("/login")
print(f"  {code}  含表单={'action=\"/login\"' in body.decode('utf-8', 'ignore')}")

print("\n⑥ POST /login 正确令牌")
code, body, hdr = req("/login", method="POST", data={"token": TOKEN}, form=True)
sc = hdr.get("Set-Cookie", "")
print(f"  {code}  Location={hdr.get('Location')}  Set-Cookie={'有' if sc else '无'}")

cookie = sc.split(";")[0] if sc else ""
print("\n⑦ 用 cookie 访问接口")
code, body, _ = req("/api/chains", cookie=cookie)
print(f"  {code}  {len(body)} 字节")

print("\n⑧ 连续错 6 次")
codes = [req("/api/search?q=x", token=f"bad{i}")[0] for i in range(6)]
print(f"  {codes}")

print("\n⑨ 被封期间用正确令牌")
code, body, _ = req("/api/search?q=%E9%80%89%E5%9D%80", token=TOKEN)
print(f"  {code}  {len(body)} 字节")

print("\n⑩ CORS 头")
_, _, hdr = req("/api/chains", token=TOKEN)
cors = [k for k in hdr if k.lower().startswith("access-control")]
print(f"  {'无 ✓' if not cors else cors}")
