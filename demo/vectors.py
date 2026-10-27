"""零依赖向量空间：bigram TF-IDF + 截断 SVD（LSA）。

它不是 bge，但它是真·分布式语义：词共现被压进低维稠密向量。
管道搭好之后，换成真模型只需替换 encode()。
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

import tb


class VectorSpace:
    def __init__(self, dim: int = 48):
        self.dim = dim
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray | None = None
        self.components: np.ndarray | None = None   # (dim, n_terms)

    # ---------- 拟合 ----------
    def fit(self, docs: list[str]) -> "VectorSpace":
        toks = [tb.tokenize(d) for d in docs]
        vocab = sorted({t for ts in toks for t in ts})
        self.vocab = {t: i for i, t in enumerate(vocab)}
        n = len(docs)
        df = Counter(t for ts in toks for t in set(ts))
        self.idf = np.array([math.log((1 + n) / (1 + df[t])) + 1.0 for t in vocab])

        X = np.zeros((n, len(vocab)), dtype=np.float64)
        for i, ts in enumerate(toks):
            for t, c in Counter(ts).items():
                X[i, self.vocab[t]] = c / max(len(ts), 1)
        X *= self.idf
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        X /= np.where(norms == 0, 1, norms)

        k = min(self.dim, max(2, min(X.shape) - 1))
        U, S, Vt = np.linalg.svd(X, full_matrices=False)
        self.components = Vt[:k]
        return self

    # ---------- 编码 ----------
    def encode(self, text: str) -> np.ndarray:
        if self.components is None:
            raise RuntimeError("call fit() first")
        v = np.zeros(len(self.vocab))
        ts = tb.tokenize(text)
        for t, c in Counter(ts).items():
            j = self.vocab.get(t)
            if j is not None:
                v[j] = c / max(len(ts), 1) * self.idf[j]
        norm = np.linalg.norm(v)
        if norm:
            v /= norm
        e = self.components @ v
        en = np.linalg.norm(e)
        return e / en if en else e

    def encode_many(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self.encode(t) for t in texts]) if texts else np.zeros((0, self.dim))


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def centroid(vecs: np.ndarray) -> np.ndarray:
    if len(vecs) == 0:
        return np.zeros(1)
    c = vecs.mean(axis=0)
    n = np.linalg.norm(c)
    return c / n if n else c
