"""把正文里的半角引号规范成中文引号（跳过代码块与行内代码）。

用法：python build/fix_quotes.py <md 路径>
"""
import re
import sys
from pathlib import Path

CJK = re.compile(r"[\u4e00-\u9fff]")
STOP = re.compile(r"——\"|\"——")


def fix(line: str) -> str:
    if '"' not in line:
        return line
    spans = []

    def keep(m):
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    masked = re.sub(r"`[^`]+`", keep, line)
    if masked.count('"') % 2 or not CJK.search(masked):
        return line
    out, opening = [], True
    for ch in masked:
        if ch == '"':
            out.append("“" if opening else "”")
            opening = not opening
        else:
            out.append(ch)
    res = "".join(out)
    for i, span in enumerate(spans):
        res = res.replace(f"\x00{i}\x00", span)
    return res


def run(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").split("\n")
    fence, changed = False, 0
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        new = fix(ln)
        if new != ln:
            lines[i] = new
            changed += 1
    path.write_text("\n".join(lines), encoding="utf-8")
    return changed


if __name__ == "__main__":
    target = Path(sys.argv[1])
    print(f"{target.name}: 修正 {run(target)} 行")
