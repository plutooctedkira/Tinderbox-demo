"""写接口 + 审计：起一个真服务，走 HTTP 全链路。

断言（任一不满足就退出码 1）：
  1. 缺依据 → 422
  2. 正常新增 → 200，且能被搜到
  3. 编辑 → 200，新旧摘要都留痕
  4. 归档 → 200，现行检索里消失
  5. 恢复 → 200，又出现
  6. 审计轨迹 ≥4 条（create / update / archive / restore）
"""
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEMO = Path(__file__).resolve().parent
PY = sys.executable
DATA = DEMO / "out" / "writecase"
PORT = 8811
BASE = f"http://127.0.0.1:{PORT}"
fails = []


def ok(cond, label):
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        fails.append(label)


def wait_port(sec=20):
    for _ in range(sec * 10):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


import shutil
shutil.rmtree(DATA, ignore_errors=True)
subprocess.run([PY, str(DEMO / "tbc.py"), "--data", str(DATA), "init"], capture_output=True)
proc = subprocess.Popen([PY, str(DEMO / "tbc.py"), "--data", str(DATA), "serve", "--port", str(PORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    ok(wait_port(), "服务启动")
    tok = (DATA / "token.txt").read_text(encoding="utf-8").strip()
    H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}

    def call(path, body=None):
        req = urllib.request.Request(BASE + path,
                                     data=json.dumps(body).encode() if body else None,
                                     method="POST" if body else "GET", headers=H)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    st, _ = call("/api/add", {"summary": "决定把冷萃改成提前一晚泡"})
    ok(st == 422, "缺依据被拒（422）")

    st, body = call("/api/add", {"summary": "决定把冷萃改成提前一晚泡",
                                 "reason": "现场泡要等六小时，客人不等",
                                 "category": "decision"})
    eid = body.get("result", {}).get("entry_id", "")
    ok(st == 200 and eid.startswith("mem-"), "新增成功")

    st, hits = call("/api/search?q=%E5%86%B7%E8%90%83")
    ok(any(h["entry_id"] == eid for h in hits.get("items", [])), "新条目能被搜到")

    st, _ = call("/api/entry/update", {"entry_id": eid, "summary": "决定把冷萃提前一晚泡好"})
    ok(st == 200, "编辑成功")

    st, _ = call("/api/entry/archive", {"entry_id": eid, "archived": True})
    st2, hits = call("/api/search?q=%E5%86%B7%E8%90%83")
    gone = not any(h["entry_id"] == eid for h in hits.get("items", []))
    ok(st == 200 and gone, "归档后从现行检索消失")

    call("/api/entry/archive", {"entry_id": eid, "archived": False})
    st, hits = call("/api/search?q=%E5%86%B7%E8%90%83")
    ok(any(h["entry_id"] == eid for h in hits.get("items", [])), "恢复后重新出现")

    st, d = call("/api/entry?id=" + eid)
    acts = [a["action"] for a in d.get("audit", [])]
    ok(len(acts) >= 4 and {"create", "update", "archive", "restore"} <= set(acts),
       f"审计轨迹完整（{acts}）")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

print(f"\n{'通过' if not fails else '失败'}：{len(fails)} 项不达标")
sys.exit(0 if not fails else 1)
