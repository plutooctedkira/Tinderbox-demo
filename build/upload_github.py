"""增量上传：只传改过的文件，复用远端已有 blob。

用法：python build/upload_github.py <token> [--dry-run]
需要 token 有 contents:write。
"""
import base64
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(r"E:\记忆库")
GIT = str(BASE / ".tools" / "mingit" / "cmd" / "git.exe")
OWNER, REPO = "plutooctedkira", "Tinderbox-demo"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
TOKEN = ARGS[0] if ARGS else ""
DRY = "--dry-run" in sys.argv
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
NEWEST_FIRST = True


def call(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "tinderbox-upload",
        "Content-Type": "application/json",
    }
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {url.split('/repos/')[-1]} → {e.code} "
                         f"{e.read()[:200].decode('utf-8', 'ignore')}")


def blob_sha(data: bytes) -> str:
    """git 的 blob 哈希：sha1('blob <len>\\0' + content)。"""
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def main():
    if not TOKEN:
        print("（未提供 token：只读对比，不会写入）")

    head = call("GET", f"{API}/commits/main")
    base_sha = head["sha"]
    print(f"远端 HEAD：{base_sha[:8]}  {head['commit']['message'].splitlines()[0][:40]}")

    remote = {}
    tree = call("GET", f"{API}/git/trees/{base_sha}?recursive=1")
    for it in tree.get("tree", []):
        if it["type"] == "blob":
            remote[it["path"]] = it["sha"]

    files = [f for f in subprocess.run(
        [GIT, "-C", str(BASE), "ls-files"], capture_output=True, text=True,
        encoding="utf-8", errors="replace").stdout.splitlines() if f.strip()]

    changed, same, added = [], 0, []
    for rel in files:
        rel = rel.replace("\\", "/")
        data = (BASE / rel).read_bytes()
        sha = blob_sha(data)
        if remote.get(rel) == sha:
            same += 1
        else:
            (added if rel not in remote else changed).append((rel, data, sha))

    deleted = sorted(set(remote) - {f.replace("\\", "/") for f in files})
    print(f"本地 {len(files)} 个 · 未变 {same} · 改动 {len(changed)} · "
          f"新增 {len(added)} · 删除 {len(deleted)}")
    for rel, _, _ in changed:
        print(f"  改 {rel}")
    for rel, _, _ in added:
        print(f"  + {rel}")
    for rel in deleted:
        print(f"  - {rel}")

    if not (changed or added or deleted):
        print("没有变化，无需提交")
        return
    if DRY:
        print("（dry-run，未上传）")
        return

    # 只上传变化的 blob，其余复用远端 sha
    entries = []
    for rel in files:
        rel_norm = rel.replace("\\", "/")
        data = (BASE / rel_norm).read_bytes()
        sha = blob_sha(data)
        if remote.get(rel_norm) != sha:
            r = call("POST", f"{API}/git/blobs",
                     {"content": base64.b64encode(data).decode(), "encoding": "base64"})
            sha = r["sha"]
        entries.append({"path": rel_norm, "mode": "100644", "type": "blob", "sha": sha})

    new_tree = call("POST", f"{API}/git/trees", {"tree": entries})
    msg = f"更新：{len(changed)} 改 / {len(added)} 增 / {len(deleted)} 删"
    commit = call("POST", f"{API}/git/commits", {
        "message": msg, "tree": new_tree["sha"], "parents": [base_sha],
        "author": {"name": "pelican", "email": "pelican@users.noreply.github.com"},
    })
    call("PATCH", f"{API}/git/refs/heads/main", {"sha": commit["sha"], "force": True})
    print(f"\n已提交 {commit['sha'][:8]} → https://github.com/{OWNER}/{REPO}")


if __name__ == "__main__":
    main()
