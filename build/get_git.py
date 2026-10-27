"""下载 MinGit（便携版 git），解压到 .tools/。不依赖 API 额度：先用 API，失败就抓 releases 页。"""
import json
import re
import urllib.request
import zipfile
from pathlib import Path

BASE = Path(r"E:\记忆库")
TOOLS = BASE / ".tools"
TOOLS.mkdir(exist_ok=True)
ZIP = TOOLS / "mingit.zip"
UA = {"User-Agent": "tinderbox-setup/1.0"}


def fetch(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(req, timeout=timeout) as r:
        return r.read()


def find_urls() -> list[str]:
    urls = []
    try:
        data = json.loads(fetch("https://api.github.com/repos/git-for-windows/git/releases/latest", 30))
        for a in data.get("assets", []):
            n = a["name"]
            if n.startswith("MinGit") and "64-bit" in n and n.endswith(".zip") and "busybox" not in n:
                urls.append(a["browser_download_url"])
        if urls:
            print(f"  来源：API（{data.get('tag_name')}）")
            return urls
    except Exception as e:
        print(f"  API 不可用（{type(e).__name__}），改抓页面")

    html = fetch("https://github.com/git-for-windows/git/releases/latest", 60).decode("utf-8", "ignore")
    m = re.findall(r'href="(/git-for-windows/git/releases/download/[^"]*?MinGit-[^"]*?64-bit\.zip)"', html)
    for h in dict.fromkeys(m):
        urls.append("https://github.com" + h)
    print(f"  来源：页面（找到 {len(urls)} 个候选）")
    return urls


if __name__ == "__main__":
    cands = find_urls()
    if not cands:
        raise SystemExit("没找到 MinGit 下载地址")
    for u in cands:
        print(f"  候选：{u.split('/')[-1]}")
    url = cands[0]
    print(f"下载 {url.split('/')[-1]} …")
    blob = fetch(url, 300)
    ZIP.write_bytes(blob)
    print(f"  完成：{len(blob) / 1024 / 1024:.1f} MB → {ZIP.relative_to(BASE)}")

    dest = TOOLS / "mingit"
    if dest.exists():
        import shutil
        shutil.rmtree(dest)
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(dest)
    exes = list(dest.rglob("git.exe"))
    print(f"  解压到 {dest.relative_to(BASE)}，git.exe 位置：{[str(p.relative_to(dest)) for p in exes]}")
