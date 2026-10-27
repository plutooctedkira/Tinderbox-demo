"""重取语料：原文存 corpus/raw，清洗结果存 corpus/clean，互不覆盖。"""
import html
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

RAW = Path(r"E:\记忆库\demo\corpus\raw")
CLEAN = Path(r"E:\记忆库\demo\corpus\clean")
RAW.mkdir(parents=True, exist_ok=True)
CLEAN.mkdir(parents=True, exist_ok=True)

PAGES = {
    "孔乙己": "https://zh.wikisource.org/wiki/%E5%AD%94%E4%B9%99%E5%B7%B1",
    "故鄉": "https://zh.wikisource.org/wiki/%E6%95%85%E9%84%89",
    "藥": "https://zh.wikisource.org/wiki/%E8%97%A5",
    "一件小事": "https://zh.wikisource.org/wiki/%E4%B8%80%E4%BB%B6%E5%B0%8F%E4%BA%8B",
}


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


def fetch(url: str, tries: int = 3) -> str:
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tinderbox-demo/0.1"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=50) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
    raise last


def clean(name: str, raw: str) -> str:
    p = Body()
    p.feed(raw)
    text = html.unescape("".join(p.parts))
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    try:
        start = next(i for i, ln in enumerate(lines) if ln == name)
    except StopIteration:
        start = 0
    body = []
    for ln in lines[start + 1:]:
        # 只有"够短又像页脚"的行才当作结束标志，避免正文被截断
        if len(body) > 5 and len(ln) < 40 and re.search(r"姊妹计划|本作品|Public domain|分類|检索结果", ln):
            break
        if re.match(r"^(作者：|作者:|此版本|發表於|发表于|目次|\d{4}年\d{0,2}月?\d{0,2}日?$)", ln):
            continue
        if len(ln) >= 2:
            body.append(ln)
    return "\n".join(body)


for name, url in PAGES.items():
    try:
        raw = fetch(url)
        (RAW / f"{name}.txt").write_text(raw, encoding="utf-8")
        text = clean(name, raw)
        if len(text) < 500:
            print(f"  ⚠ {name}: 清洗后只剩 {len(text)} 字，保留原文待查")
            continue
        (CLEAN / f"{name}.txt").write_text(text, encoding="utf-8")
        print(f"  ✓ {name:<8}{len(text):>6} 字   {text[:26]}…")
    except Exception as e:
        print(f"  ✗ {name:<8}{type(e).__name__}: {str(e)[:50]}")

tot = sum(len((p.read_text(encoding='utf-8'))) for p in CLEAN.glob("*.txt"))
print(f"\n清洗后合计 {tot} 字")
