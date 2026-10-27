"""备份 / 恢复闭环。

断言：
  1. backup 退出码 0，校验通过
  2. 备份出来的库条目数与源一致
  3. 人为删除后条目变少
  4. restore 后条目数恢复
  5. 恢复后 tbc check 通过
"""
import shutil
import subprocess
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent
PY = sys.executable
DATA = DEMO / "out" / "backupcase"
fails = []


def ok(cond, label):
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        fails.append(label)


def cli(*args, input_text=None):
    r = subprocess.run([PY, str(DEMO / "tbc.py"), "--data", str(DATA), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", input=input_text)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


shutil.rmtree(DATA, ignore_errors=True)
cli("init")
seed = DEMO / "seed_notes"
cli("ingest", str(seed))

sys.path.insert(0, str(DEMO))
import tb  # noqa: E402

tb.DB_PATH = DATA / "memory.db"
tb.ARCHIVE = DATA / "l0"
conn = tb.connect()
before = tb.stats(conn)["entries"]
conn.close()
print(f"  初始条目 {before}")

code, out = cli("backup")
ok(code == 0 and "校验 通过" in out, "备份并自检通过")

backup = sorted([p for p in (DATA / "backup").iterdir() if p.name[0].isdigit()])[-1]
manifest = (backup / "manifest.json").read_text(encoding="utf-8")
ok(f'"entries": {before}' in manifest, "备份清单条目数一致")

conn = tb.connect()
with tb.tx(conn):
    conn.execute("DELETE FROM memory_entries WHERE row_id % 2 = 0")
mid = tb.stats(conn)["entries"]
conn.close()
ok(mid < before, f"人为破坏后条目减少（{mid}）")

code, out = cli("restore", str(backup), "--force", input_text="y\n")
ok(code == 0, "恢复退出码 0")

conn = tb.connect()
after = tb.stats(conn)["entries"]
conn.close()
ok(after == before, f"恢复后条目还原（{after} vs {before}）")

code, out = cli("check")
ok(code == 0 and "通过" in out, "恢复后结构自检通过")

print(f"\n{'通过' if not fails else '失败'}：{len(fails)} 项不达标")
sys.exit(0 if not fails else 1)
