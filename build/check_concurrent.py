"""检查三：并发写。两个进程同时往一个库灌，看会不会锁死或丢数据。"""
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r"E:\记忆库\demo")
import tb

DATA = Path(r"E:\记忆库\.conc")
CLI = r"E:\记忆库\demo\tbc.py"
shutil.rmtree(DATA, ignore_errors=True)
subprocess.run([sys.executable, CLI, "--data", str(DATA), "init"], capture_output=True)


def make(tag, n=8):
    p = Path(rf"E:\记忆库\.tmp\conc_{tag}.md")
    p.parent.mkdir(exist_ok=True)
    lines = [f"# 并发测试 {tag}"]
    for i in range(n):
        lines.append(f"决定：{tag} 的第 {i} 条结论——因为并发写入要保证不丢。")
    p.write_text("\n\n".join(lines), encoding="utf-8")
    return p


A, B = make("A"), make("B")


def run(path):
    t0 = time.time()
    r = subprocess.run([sys.executable, CLI, "--data", str(DATA), "ingest", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    added = "?"
    for line in out.splitlines():
        if "新增" in line:
            added = line.strip()
    return r.returncode, round(time.time() - t0, 2), added, out


print("=== 并发跑三轮，每轮两个进程同时写 ===")
for round_no in range(1, 4):
    with ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(run, [A, B]))
    for code, ms, added, out in results:
        flag = "✓" if code == 0 else "✗"
        lock = "database is locked" in out
        print(f"  第{round_no}轮 {flag} {ms:>5}s  {added}  锁定错误={'有' if lock else '无'}")

tb.DB_PATH = DATA / "memory.db"
tb.ARCHIVE = DATA / "l0"
conn = tb.connect()
st = tb.stats(conn)
print(f"\n最终：材料 {st['documents']} · 条目 {st['entries']}（期望 2 材料 48 条）")
dup = conn.execute("SELECT l1_summary, count(*) c FROM memory_entries "
                   "GROUP BY l1_summary HAVING c > 1").fetchall()
print(f"重复条目：{len(dup)} 组" + ("" if not dup else " ⚠"))
conn.close()

r = subprocess.run([sys.executable, CLI, "--data", str(DATA), "check"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("\n" + (r.stdout or "").strip()[-260:])
