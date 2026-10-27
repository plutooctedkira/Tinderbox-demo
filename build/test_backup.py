"""验备份恢复闭环：备份 → 校验 → 破坏 → 恢复 → 内容一致。"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"E:\记忆库\demo")
import tb

PY = sys.executable
CLI = r"E:\记忆库\demo\tbc.py"
DATA = Path(r"E:\记忆库\.vault")


def cli(*args, input_text=None):
    r = subprocess.run([PY, CLI, "--data", str(DATA), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", input=input_text)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


tb.DB_PATH = DATA / "memory.db"
tb.ARCHIVE = DATA / "l0"
conn = tb.connect()
before = tb.stats(conn)
conn.close()
print(f"恢复前：条目 {before['entries']} · 材料 {before['documents']}")

code, out = cli("backup")
print(out)

backups = sorted((DATA / "backup").iterdir())
latest = [b for b in backups if b.name[0].isdigit()][-1]
print(f"\n取最新备份 {latest.name}")

# 破坏：删掉一半记忆
conn = tb.connect()
with tb.tx(conn):
    conn.execute("DELETE FROM memory_entries WHERE row_id % 2 = 0")
mid = tb.stats(conn)
conn.close()
print(f"人为删除后：条目 {mid['entries']}（原 {before['entries']}）")

code, out = cli("restore", str(latest), "--force")
print(out)

conn = tb.connect()
after = tb.stats(conn)
conn.close()
print(f"恢复后：条目 {after['entries']} · 材料 {after['documents']} · FTS {after['fts_active']}")
ok = after["entries"] == before["entries"] and after["documents"] == before["documents"]
print("一致 ✓" if ok else "不一致 ✗")

code, out = cli("check")
print("\n" + out.splitlines()[-1])
