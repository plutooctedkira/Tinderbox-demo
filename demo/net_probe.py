import json
import urllib.error
import urllib.request

TESTS = [
    ("直连", None),
    ("走本地代理 127.0.0.1:7897", "http://127.0.0.1:7897"),
]
URL = "https://api.deepseek.com/v1/models"


def probe(proxy):
    if proxy:
        op = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(URL, headers={"User-Agent": "tinderbox-demo/0.1"})
    try:
        with op.open(req, timeout=12) as r:
            return f"HTTP {r.status}", r.read()[:120]
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}（可达，未带 key）", e.read()[:120]
    except Exception as e:
        return f"失败: {type(e).__name__}: {str(e)[:90]}", b""


for label, proxy in TESTS:
    status, body = probe(proxy)
    print(f"{label:<28} {status}")
    if body:
        print("    ", body.decode("utf-8", "ignore").replace("\n", " ")[:110])
