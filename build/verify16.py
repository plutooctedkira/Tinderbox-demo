"""验收 v2.16 的改动是否真的落进文档。"""
import ast
import re
from pathlib import Path

MD = Path(r"E:\记忆库\Tinderbox_记忆库完整方案_v2.16.md")
text = MD.read_text(encoding="utf-8")
lines = text.split("\n")

print("【1】页面表")
seg = [ln for ln in lines if re.match(r"^\| \d+ \| ", ln)]
pages = [ln for ln in seg if "/api/" in ln and ("演变" in ln or "星网" in ln or "搜索" in ln
                                               or "冲突" in ln or "详情" in ln)]
print(f"  核心页面行 {len(pages)} 条；非必要说明 {'有' if '非必要页面' in text else '无'}")

print("\n【2】模块表优先级")
prio = re.findall(r"\|\s*(★ 核心|○ 可选)\s*\|", text)
from collections import Counter
print(f"  {dict(Counter(prio))}")

print("\n【3】路线表")
for ln in lines:
    if "人日" in ln and ("合计" in ln or "核心" in ln):
        print("  ", ln.strip()[:80])
print("  含 P4：", "是" if re.search(r"\|\s*\*?\*?P4", text) else "否")
print("  非必要功能表：", "有" if "不进主计划，按需启动" in text else "无")

print("\n【4】部署章范围声明：", "有" if "本机或一台 VPS 单机部署即可" in text else "无")

print("\n【5】python 代码块可解析性")
fences = [i for i, ln in enumerate(lines) if ln.strip().startswith("```")]
ok = bad = 0
for a, b in zip(fences[::2], fences[1::2]):
    if lines[a].strip().strip("`").strip() != "python":
        continue
    try:
        ast.parse("\n".join(lines[a + 1:b]))
        ok += 1
    except SyntaxError as e:
        bad += 1
        print(f"   行{a + 2} {e.msg}")
print(f"  可解析 {ok}，失败 {bad}")

print("\n【6】残留检查")
for kw in ("9 个页面", "P4 锦上添花", "33 人日（单人）"):
    print(f"  「{kw}」：{'仍在' if kw in text else '已清除'}")
