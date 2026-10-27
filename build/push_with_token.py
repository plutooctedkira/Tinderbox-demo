"""把 E:\\记忆库 推到 GitHub。

这台机器上 git 出网有三个坑（都已处理）：
  1. 直连 GitHub 不通 → 必须走本地代理 127.0.0.1:7897
  2. 默认 schannel 后端拿不到凭证句柄 → 换 openssl + 指定 CA
  3. credential helper 依赖 sh.exe，沙箱里跑不起来 → 用 Authorization 头
     （URL 内联凭证会偶发 TLS EOF，用头部稳定）

用法：python build/push_with_token.py ["提交说明"] [--no-commit]
"""
import base64
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(r"E:\记忆库")
GIT = r"D:\Git\cmd\git.exe"
TOKEN_FILE = BASE / ".github_token"
PROXY = "http://127.0.0.1:7897"
CA = r"D:\Git\ucrt64\etc\ssl\certs\ca-bundle.crt"
REPO = "https://github.com/plutooctedkira/Tinderbox-demo"


def token() -> str:
    raw = TOKEN_FILE.read_text(encoding="ascii").strip()
    m = re.search(r":([^@]+)@", raw)
    return m.group(1) if m else raw


def flags() -> list[str]:
    b64 = base64.b64encode(f"x-access-token:{token()}".encode()).decode()
    return ["-c", f"http.proxy={PROXY}", "-c", f"https.proxy={PROXY}",
            "-c", "http.sslBackend=openssl", "-c", f"http.sslCAInfo={CA}",
            "-c", f"http.extraheader=AUTHORIZATION: basic {b64}"]


def run(*args, quiet=False):
    p = subprocess.run([GIT, "-C", str(BASE), *flags(), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((p.stdout or "") + (p.stderr or "")).replace(token(), "***")
    if not quiet:
        keep = [ln for ln in out.splitlines()
                if re.search(r"->|error|fatal|rejected|up-to-date|To https", ln)]
        print("\n".join(keep[:8]))
    return p.returncode


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    msg = args[0] if args else None

    if "--no-commit" not in sys.argv:
        subprocess.run([GIT, "-C", str(BASE), "add", "-A"], capture_output=True)
        st = subprocess.run([GIT, "-C", str(BASE), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.strip()
        if st:
            run("commit", "-q", "-m", msg or "update", quiet=True)
            print(f"已提交：{msg or 'update'}")

    if run("push", "origin", "main") != 0:
        print("✗ 推送失败")
        return 1

    run("fetch", "origin", quiet=True)
    head = subprocess.run([GIT, "-C", str(BASE), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()[:8]
    remote = subprocess.run([GIT, "-C", str(BASE), "rev-parse", "origin/main"],
                            capture_output=True, text=True).stdout.strip()[:8]
    ok = head == remote
    print(f"{'✓ 已同步' if ok else '⚠ 不一致'}  本地 {head} / 远端 {remote}  {REPO}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
