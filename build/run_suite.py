"""跑完整测试套件，把每项的输出、耗时、退出码存成结构化结果。

产物：
  demo/out/suite/<name>.log   每项的完整输出
  demo/out/suite/suite.json   汇总（名称/退出码/耗时/关键指标行）
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(r"E:\记忆库")
DEMO = BASE / "demo"
OUT = DEMO / "out" / "suite"
PY = sys.executable
OUT.mkdir(parents=True, exist_ok=True)

# (id, 标题, 命令, 超时秒)
CASES = [
    ("demo", "主流程（LLM 精修）", [PY, str(DEMO / "run_demo.py")], 300),
    ("demo2", "主流程二次运行（验证可复现）", [PY, str(DEMO / "run_demo.py")], 300),
    ("complement", "补充记忆（不动原有记录）", [PY, str(DEMO / "run_complement.py")], 300),
    ("selftest", "不变量自测（12 项）", [PY, str(DEMO / "selftest.py")], 120),
    ("offline", "离线写入 / 异步精修 / 浮现 / Markdown", [PY, str(DEMO / "run_offline.py")], 300),
    ("maintenance", "TTL 回收（分档 / 幂等）", [PY, str(DEMO / "run_maintenance.py")], 180),
    ("eval", "评估（检索 + 冲突判定）", [PY, str(DEMO / "run_eval.py")], 300),
    ("auth", "鉴权（10 项）", [PY, str(DEMO / "test_auth.py")], 120),
    ("cli_check", "维护 CLI：结构自检", [PY, str(DEMO / "maintenance.py"), "check"], 120),
    ("cli_decay", "维护 CLI：衰减（dry-run）", [PY, str(DEMO / "maintenance.py"), "decay"], 120),
    ("cli_reclaim", "维护 CLI：回收（dry-run）", [PY, str(DEMO / "maintenance.py"), "reclaim"], 120),
    ("probe_concept", "概念挂靠标定", [PY, str(DEMO / "concept_probe.py")], 180),
    ("write", "看板写入：新增/编辑/归档/审计", [PY, str(DEMO / "test_write.py")], 180),
    ("backup", "备份与恢复闭环", [PY, str(DEMO / "test_backup.py")], 240),
    ("topic", "按材料名检索（门槛 R@1 60%）", [PY, str(DEMO / "test_topic.py")], 240),
]

results = []
for cid, title, cmd, timeout in CASES:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", cwd=str(DEMO))
        code, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        code, out = -9, "TIMEOUT"
    ms = (time.time() - t0) * 1000
    (OUT / f"{cid}.log").write_text(out, encoding="utf-8")
    results.append({"id": cid, "title": title, "exit": code,
                    "ms": round(ms), "lines": len(out.splitlines())})
    print(f"{'✓' if code == 0 else '✗'} {cid:<14}{ms:>7.0f} ms  ({len(out.splitlines())} 行)")

# 确定性对比：两次 demo 的日志
det = {"checked": False}
try:
    import re
    ID = re.compile(r"\b(mem|c|g|k|r|rv)-[0-9a-f]{6,}\b")
    NUM = re.compile(r"\d+(?:\.\d+)?")
    DASH = re.compile(r"─{3,}")

    def norm(txt):
        lines = []
        for ln in txt.splitlines():
            if not ln.strip():
                continue
            ln = DASH.sub("─…", ID.sub("ID", ln))
            lines.append(NUM.sub("#", ln))
        return lines

    a = norm((OUT / "demo.log").read_text(encoding="utf-8"))
    b = norm((OUT / "demo2.log").read_text(encoding="utf-8"))
    det = {"checked": True, "identical": a == b, "lines": len(a), "lines2": len(b)}
except Exception as e:
    det["error"] = f"{type(e).__name__}: {e}"

summary = {"ran_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": results,
           "determinism": det, "total_ms": sum(r["ms"] for r in results)}
(OUT / "suite.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n确定性：{'一致' if det.get('identical') else '不一致' if det.get('checked') else '未检查'}"
      f"（两次 {det.get('lines')} 行）")
print(f"总耗时 {summary['total_ms'] / 1000:.1f} 秒 · 结果写入 {OUT / 'suite.json'}")
