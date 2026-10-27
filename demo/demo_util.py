"""demo 脚本共用的输出工具（原先在两个脚本里各写了一份）。"""
from __future__ import annotations

import sys


class Tee:
    """同时写屏幕和日志文件。"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def rule(title: str = ""):
    """分节横线。"""
    print(f"\n── {title} " + "─" * max(0, 68 - len(title) * 2) if title else "\n" + "─" * 74)


def kv(label: str, value, width: int = 20):
    print(f"  {label:<{width}}{value}")


class capture:
    """把 stdout 同时镜像到日志文件（with 语句用法）。"""

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def __enter__(self):
        self.f = open(self.path, "w", encoding="utf-8")
        self.saved = sys.stdout
        sys.stdout = Tee(self.saved, self.f)
        return self

    def __exit__(self, *exc):
        sys.stdout = self.saved
        self.f.close()
        return False
