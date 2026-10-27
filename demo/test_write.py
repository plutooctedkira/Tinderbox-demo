"""编辑/归档闭环 + 「不允许新增」的守门测试。

断言：
  1. /api/add 已不存在（404/405）
  2. 编辑摘要成功，且能被搜到新词
  3. 归档后从现行检索消失，恢复后回来
  4. 审计轨迹含 update / archive / restore
"""
import json
import shutil
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


shutil.rmtree(DATA, ignore_errors=True)
subprocess.run([PY, str(DEMO / "tbc.py"), "--data", str(DATA), "init"], capture_output=True)
subprocess.run([PY, str(DEMO / "tbc.py"), "--data", str(DATA), "ingest",
                str(DEMO / "seed_notes" / "05_定价.md")], capture_output=True)

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

    st, _ = call("/api/add", {"summary": "想绕过面板新增", "reason": "试试还能不能加"})
    ok(st in (404, 405), f"新增接口已关闭（{st}）")

    st, hits = call("/api/search?q=%E6%8B%BF%E9%93%81")
    eid = hits["items"][0]["entry_id"]
    ok(bool(eid), "找到一条可编辑的记忆")

    st, _ = call("/api/entry/update", {"entry_id": eid, "summary": "美式 15，拿铁 21，单品手冲 25。"})
    ok(st == 200, "编辑成功")
    st, hits = call("/api/search?q=21")
    ok(any(h["entry_id"] == eid for h in hits.get("items", [])), "编辑后新词可检索")

    st, _ = call("/api/entry/archive", {"entry_id": eid, "archived": True})
    st2, hits = call("/api/search?q=21")
    ok(st == 200 and not any(h["entry_id"] == eid for h in hits.get("items", [])),
       "归档后从现行检索消失")

    call("/api/entry/archive", {"entry_id": eid, "archived": False})
    st, hits = call("/api/search?q=21")
    ok(any(h["entry_id"] == eid for h in hits.get("items", [])), "恢复后重新出现")

    st, d = call("/api/entry?id=" + eid)
    acts = {a["action"] for a in d.get("audit", [])}
    ok({"update", "archive", "restore"} <= acts, f"审计轨迹完整（{sorted(acts)}）")
    # 面板导入：试跑不写库、真跑入库、重复导入幂等
    seed_dir = str(DEMO / "seed_notes")
    st, dry = call("/api/import", {"path": seed_dir, "dry_run": True})
    ok(st == 200 and dry["stats"]["added"] > 0 and dry["stats"]["entries"] == 0,
       "面板导入：试跑不写库")

    st, real = call("/api/import", {"path": seed_dir, "project": "测试项目"})
    ok(st == 200 and real["stats"]["entries"] > 0, f"面板导入：真跑写入 {real['stats']['entries']} 条")

    st, again = call("/api/import", {"path": seed_dir, "project": "测试项目"})
    ok(st == 200 and again["stats"]["added"] == 0, "面板导入：重复导入不重复写")

    st, conc = call("/api/concepts")
    roots = [x for x in conc["items"] if x["parent_id"] is None]
    ok(any(r["name"] == "测试项目" for r in roots), "面板导入：项目成为星网根节点")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

print(f"\n{'通过' if not fails else '失败'}：{len(fails)} 项不达标")
sys.exit(0 if not fails else 1)
