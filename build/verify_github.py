"""验证上传结果：文件数、敏感文件、提交数。"""
import json
import sys
import urllib.error
import urllib.request

OWNER, REPO = "plutooctedkira", "Tinderbox-demo"
TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
API = f"https://api.github.com/repos/{OWNER}/{REPO}"


def get(url, auth=True):
    h = {"Accept": "application/vnd.github+json", "User-Agent": "verify"}
    if auth:
        h["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=h)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


st, root = get(f"{API}/contents/")
print(f"顶层：{st} · {len(root)} 项")
for it in sorted(root, key=lambda x: x["name"]):
    print(f"  {'[dir] ' if it['type'] == 'dir' else '      '}{it['name']}")

st_env, _ = get(f"{API}/contents/demo/.env")
st_ex, _ = get(f"{API}/contents/demo/.env.example")
print(f"\ndemo/.env        → {st_env}  {'✓ 未上传' if st_env == 404 else '⚠ 泄漏了'}")

st_c, commits = get(f"{API}/commits?per_page=10")
print(f"提交数：{len(commits)}（历史里只应有一个）")
for c in commits:
    print(f"  {c['sha'][:8]}  {c['commit']['message'].splitlines()[0]}")

ph, _ = get(f"{API}/contents/PLACEHOLDER.txt")
print(f"占位文件 PLACEHOLDER.txt → {ph}  {'✓ 已不在树里' if ph == 404 else '⚠ 还在'}")
