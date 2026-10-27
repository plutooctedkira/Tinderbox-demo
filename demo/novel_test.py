"""从 corpus/raw 重清洗 → 灌库（规则提炼）→ 看块数、L0、提炼质量、检索。"""
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

RAW = Path(r"E:\记忆库\demo\corpus\raw")
CLEAN = Path(r"E:\记忆库\demo\corpus\clean")
CLEAN.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, r"E:\记忆库\demo")
import tb  # noqa: E402


class Body(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "") or ""
        if self.depth == 0 and tag == "div" and "mw-parser-output" in cls:
            self.depth = 1
            return
        if self.depth:
            if tag in ("script", "style"):
                self.skip += 1
            elif tag == "div":
                self.depth += 1
            elif tag in ("p", "br", "li", "h1", "h2", "h3"):
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.skip and tag in ("script", "style"):
            self.skip -= 1
            return
        if self.depth and tag == "div":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)


HEADER = re.compile(r"收錄|收录|姊妹计划|本作品|维基|维基|初刊|Public domain|分類|目次|^作者")
FOOTER = re.compile(r"姊妹计划|本作品|Public domain|分類|检索结果")


def clean(name: str, raw: str) -> str:
    p = Body()
    p.feed(raw)
    lines = [ln.strip() for ln in html.unescape("".join(p.parts)).split("\n") if ln.strip()]
    try:
        start = next(i for i, ln in enumerate(lines) if ln == name)
    except StopIteration:
        start = 0
    body: list[str] = []
    for ln in lines[start + 1:]:
        if not body:                      # 还没进入正文：跳过标题/导航/版权说明
            if len(ln) < 20 or HEADER.search(ln):
                continue
            body.append(ln)
            continue
        if len(ln) < 40 and FOOTER.search(ln):
            break
        body.append(ln)
    return "\n".join(body)


texts = {}
print("【清洗】")
for p in sorted(RAW.glob("*.txt")):
    t = clean(p.stem, p.read_text(encoding="utf-8"))
    if len(t) < 500:
        print(f"  ⚠ {p.stem}: 只剩 {len(t)} 字")
        continue
    (CLEAN / f"{p.stem}.txt").write_text(t, encoding="utf-8")
    texts[p.stem] = t
    print(f"  {p.stem:<8}{len(t):>6} 字   {t[:30]}…")
print(f"  合计 {sum(len(t) for t in texts.values())} 字\n")

tb.DB_PATH = CLEAN.parent / "novel.db"
for f in (tb.DB_PATH, Path(str(tb.DB_PATH) + "-wal"), Path(str(tb.DB_PATH) + "-shm")):
    f.unlink(missing_ok=True)
conn = tb.init_db(reset=True)

print("【灌入（规则提炼）】")
n_chunk = 0
for name, text in texts.items():
    chunks = tb.split_semantic(text)
    n_chunk += len(chunks)
    res = tb.ingest(conn, text, title=name)
    print(f"  {name:<8}{len(chunks):>3} 块 → {len(res['entries']):>3} 条 L1")

st = tb.stats(conn)
print(f"\n  条目 {st['entries']} · 块 {n_chunk} · L0 {st['l0_bytes']:,} 字节"
      f"（原文 {st['l0_raw']:,}，{st['l0_raw'] / max(st['l0_bytes'], 1):.2f}:1）")

print("\n【提炼出的 L1（看质量）】")
for r in conn.execute("SELECT category, l1_summary FROM memory_entries LIMIT 10"):
    print(f"  [{r['category']:<10}] {r['l1_summary'][:54]}")

print("\n【检索】")
for q in ("孔乙己", "茴香豆", "长衫", "閏土"):
    hits = tb.search(conn, q, top_k=2)
    print(f"  查「{q}」→ {len(hits)} 条" + (f"：{hits[0]['l1_summary'][:34]}" if hits else ""))
conn.close()
