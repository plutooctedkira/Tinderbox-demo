"""静态体检：函数长度、未被调用的函数、循环里的 SQL、重复代码。"""
from __future__ import annotations

import ast
import re
from pathlib import Path

DEMO = Path(r"E:\记忆库\demo")
FILES = ["tb.py", "web.py", "run_demo.py", "run_complement.py", "vectors.py",
         "api_client.py", "concept_probe.py", "vector_probe.py"]

all_src = {f: (DEMO / f).read_text(encoding="utf-8") for f in FILES}
names_called: set[str] = set()
for src in all_src.values():
    names_called.update(re.findall(r"\b([a-zA-Z_]\w*)\s*\(", src))

print(f"{'文件':<20}{'行数':>6}{'函数':>6}{'最长函数':>10}")
for f, src in all_src.items():
    tree = ast.parse(src)
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    longest = max(((n.end_lineno or n.lineno) - n.lineno + 1, n.name) for n in fns) if fns else (0, "-")
    print(f"{f:<20}{len(src.splitlines()):>6}{len(fns):>6}{longest[1] + ' ' + str(longest[0]) + '行':>16}")

print("\n【一】超过 60 行的函数")
for f, src in all_src.items():
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ln = (n.end_lineno or n.lineno) - n.lineno + 1
            if ln > 60:
                print(f"  {f:<20}{n.name:<28}{ln} 行（第 {n.lineno} 行起）")

print("\n【二】定义了但没人调用的函数（可能是死代码）")
for f, src in all_src.items():
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if len(re.findall(rf"\b{n.name}\s*\(", "\n".join(all_src.values()))) <= 1:
                print(f"  {f:<20}{n.name}")

print("\n【三】for 循环里直接 execute（N+1 查询）")
for f, src in all_src.items():
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"\s*for .*:", line):
            block = lines[i + 1:i + 6]
            if any("conn.execute" in b or "fetch(" in b for b in block):
                print(f"  {f}:{i + 1}  {line.strip()[:60]}")

print("\n【四】重复定义的常量/工具")
for key in ("def rule(", "class Tee", "def now(", "def _clip(", "def tokenize("):
    hits = [f for f, s in all_src.items() if key in s]
    if len(hits) > 1:
        print(f"  {key!r} 出现在: {', '.join(hits)}")
