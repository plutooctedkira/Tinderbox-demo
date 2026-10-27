"""方案体检 第二轮：代码块真伪、常量冲突上下文、章节存在性。"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

MD = Path(r"E:\记忆库\Tinderbox_记忆库完整方案_v2.15.md")
text = MD.read_text(encoding="utf-8")
lines = text.split("\n")

fences = [i for i, ln in enumerate(lines) if ln.strip().startswith("```")]
blocks = [(lines[a].strip().strip("`").strip() or "none", a + 1, lines[a + 1:b])
          for a, b in zip(fences[::2], fences[1::2])]

print("【一】代码块能不能真的跑")
py_ok = py_bad = js_ok = js_bad = 0
bad_py = []
for lang, ln, body in blocks:
    src = "\n".join(body)
    if lang == "python":
        try:
            ast.parse(src)
            py_ok += 1
        except SyntaxError as e:
            py_bad += 1
            bad_py.append((ln, str(e).split("(")[0][:40], body[0][:50] if body else ""))
    elif lang == "json":
        try:
            json.loads(src)
            js_ok += 1
        except Exception:
            js_bad += 1
print(f"  python 块 {py_ok + py_bad}：可解析 {py_ok}，语法不完整 {py_bad}")
for ln, err, sample in bad_py[:6]:
    print(f"    行{ln:>5} {err:<34}{sample}")
print(f"  json 块：合法 {js_ok}，不合法 {js_bad}（多为带注释的示意）")

# 函数体是 ... 的"签名块"
stubs = []
for lang, ln, body in blocks:
    if lang != "python":
        continue
    src = "\n".join(body)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            body_src = [ast.dump(x) for x in n.body]
            if len(n.body) == 1 and isinstance(n.body[0], ast.Expr) and \
                    isinstance(n.body[0].value, ast.Constant) and n.body[0].value.value is Ellipsis:
                stubs.append((ln, n.name))
print(f"\n【二】只有签名、函数体是 `...` 的：{len(stubs)} 个")
for ln, name in stubs[:10]:
    print(f"    行{ln:>5}  {name}()")

# 常量冲突上下文
print("\n【三】EMBED_DIM 出现在哪")
for i, ln in enumerate(lines, 1):
    if "EMBED_DIM" in ln or ("512" in ln and "维" in ln) or ("1024" in ln and "维" in ln):
        print(f"  行{i:>5}  {ln.strip()[:96]}")

# 章节存在性
print("\n【四】几个关键小节是否存在")
for key in ("6.10.2", "6.10.3", "6.9.4", "6.9.5", "5.19", "5.20", "11.1", "11.2"):
    hit = [ln.strip()[:60] for ln in lines if re.match(rf"^#{{2,4}}\s*{re.escape(key)}\b", ln.strip())]
    print(f"  {key:<8}{'✓ ' + hit[0] if hit else '✗ 没有这个小节标题'}")

# 模块表 vs demo 实现
print("\n【五】第 6 章列了多少模块")
mods = [ln for ln in lines if re.match(r"^\|\s*\d+\s*\|\s*`?[a-z_]+\.py", ln)]
print(f"  模块表行数 {len(mods)}")
for m in mods[:40]:
    print("   ", m.split("|")[2].strip()[:44])
