"""OpenAI 兼容 API 的最小客户端（只用标准库）。

用途两件事：
  1. llm()     —— 把 demo 里"规则提炼"换成真 LLM 提炼（验 L1 质量）
  2. embed()   —— 真嵌入模型（验语义泛化）

配置放 demo/.env，不写进代码：
    LLM_BASE_URL=https://api.deepseek.com/v1
    LLM_API_KEY=sk-...
    LLM_MODEL=deepseek-chat

    EMBED_BASE_URL=https://api.siliconflow.cn/v1
    EMBED_API_KEY=sk-...
    EMBED_MODEL=BAAI/bge-m3

自检：python demo/api_client.py --check
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"
CACHE = BASE / "out" / "llm_cache"
STATS = {"hit": 0, "miss": 0}


def cache_enabled() -> bool:
    if "--no-cache" in sys.argv or os.environ.get("LLM_CACHE") == "off":
        return False
    return True


def _cache_key(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cache_stats() -> dict:
    return dict(STATS)


def reset_stats():
    STATS.update(hit=0, miss=0)


def load_env() -> dict:
    conf: dict[str, str] = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            conf[k.strip()] = v.strip()
    return conf


def _post(url: str, key: str, payload: dict, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}",
                 "User-Agent": "tinderbox-demo/0.1"},
        method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chat(prompt: str, *, system: str = "", conf: dict | None = None,
         temperature: float = 0.0, max_tokens: int = 1200) -> str:
    conf = conf or load_env()
    base = conf.get("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    key = conf.get("LLM_API_KEY", "")
    model = conf.get("LLM_MODEL", "deepseek-chat")
    if not key:
        raise RuntimeError("LLM_API_KEY 未配置（见 demo/.env.example）")
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": msgs,
               "temperature": temperature, "max_tokens": max_tokens}
    path = CACHE / (_cache_key(payload) + ".json")
    if cache_enabled() and path.exists():
        STATS["hit"] += 1
        return json.loads(path.read_text(encoding="utf-8"))["text"]

    data = _post(f"{base}/chat/completions", key, payload)
    text = data["choices"][0]["message"]["content"]
    STATS["miss"] += 1
    if cache_enabled():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "model": model, "temperature": temperature,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "prompt": msgs[-1]["content"][:200],
            "usage": data.get("usage"),
            "text": text,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    return text


def embed(texts: list[str], *, conf: dict | None = None) -> list[list[float]]:
    conf = conf or load_env()
    base = conf.get("EMBED_BASE_URL", "").rstrip("/")
    key = conf.get("EMBED_API_KEY", "")
    model = conf.get("EMBED_MODEL", "BAAI/bge-m3")
    if not (base and key):
        raise RuntimeError("EMBED_BASE_URL / EMBED_API_KEY 未配置")
    data = _post(f"{base}/embeddings", key, {"model": model, "input": texts})
    return [d["embedding"] for d in data["data"]]


def _check():
    conf = load_env()
    print(f"配置文件：{ENV}（{'存在' if ENV.exists() else '不存在'}）")
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "EMBED_BASE_URL", "EMBED_MODEL", "EMBED_API_KEY"):
        v = conf.get(k, "")
        shown = f"{v[:6]}…（{len(v)} 位）" if k.endswith("KEY") and v else (v or "—")
        print(f"  {k:<16}{shown}")

    print("\n[1] 能不能调 LLM：")
    try:
        out = chat("只回答两个字：你好", max_tokens=10, conf=conf)
        print(f"  ✓ {out.strip()[:40]}")
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {str(e)[:120]}")

    print("\n[2] 能不能算向量：")
    try:
        vecs = embed(["测试一句话"], conf=conf)
        print(f"  ✓ 维度 {len(vecs[0])}")
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {str(e)[:120]}")
        print("     说明：DeepSeek 目前不提供 embeddings；换成硅基流动/智谱/OpenAI 的兼容端点")


if __name__ == "__main__":
    if "--check" in sys.argv:
        _check()
    else:
        print("用法：python demo/api_client.py --check")
