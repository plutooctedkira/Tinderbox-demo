"""把 E:\\记忆库 推到 GitHub。

这台机器上 git 出网需要三个额外设置（缺一不可）：
  1. http.proxy           —— 直连 GitHub 不通，必须走本地代理
  2. http.sslBackend=openssl —— 默认 schannel 拿不到凭证句柄
  3. 凭证用 URL 内联 —— credential helper 依赖 sh.exe，沙箱里跑不起来

用法：python build/push_with_token.py ["提交说明"] [--no-commit]
"""
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(r"E:\记忆库")
GIT = r"D:\Git\cmd\git.exe"
TOKEN_FILE = BASE / ".github_token"
PROXY = "http://127.0.0.1:7897"
CA = r"D:\Git\ucrt64\etc\ssl\certs\ca-bundle.crt"
REMOTE = "https://github.com/plutooctedkira/Tinderbox-demo.git"

FLAGS = ["-c", f"http.proxy={PROXY}", "-c", f"https.proxy={PROXY}",
         "-c", "http.sslBackend=openssl", "-c", f"http.sslCAInfo={CA}"]


def token() -> str:
    raw = TOKEN_FILE.read_text(encoding="ascii").strip()
    m = re.search(r":([^@]+)@", raw)
    return m.group(1) if m else raw


def run(*args, quiet=False):
    p = subprocess.run([GIT, "-C", str(BASE), *FLAGS, *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((p.stdout or "") + (p.stderr or "")).replace(token(), "***")
    out = re.sub(r"https://[^@\s]+@", "https://***@", out)
    if not quiet:
        print(out.strip()[:600])
    return p.returncode, out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    msg = args[0] if args else None

    if "--no-commit" not in sys.argv:
        code, _ = run("add", "-A", quiet=True)
        st = subprocess.run([GIT, "-C", str(BASE), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.strip()
        if st:
            run("commit", "-q", "-m", msg or "update", quiet=True)
            print(f"已提交：{msg or 'update'}")

    url = REMOTE.replace("https://", f"https://x-access-token:{token()}@")
    code, out = run("push", url, "main")
    if code != 0:
        print(f"\n✗ 推送失败（退出码 {code}）")
        return 1

    run("fetch", "origin", quiet=True)
    head = subprocess.run([GIT, "-C", str(BASE), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()[:8]
    remote = subprocess.run([GIT, "-C", str(BASE), "rev-parse", "origin/main"],
                            capture_output=True, text=True).stdout.strip()[:8]
    print(f"\n{'✓ 已同步' if head == remote else '⚠ 不一致'}  本地 {head} / 远端 {remote}")
    print(f"https://github.com/plutooctedkira/Tinderbox-demo")
    return 0 if head == remote else 1


if __name__ == "__main__":
    sys.exit(main())
