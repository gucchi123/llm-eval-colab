"""小さな BM25（文字 2-gram）。日本語を形態素解析なしで検索するための最小の作り。"""
from __future__ import annotations

import math
import unicodedata
from collections import Counter


def grams(text: str) -> list[str]:
    s = unicodedata.normalize("NFKC", text)
    s = "".join(ch for ch in s if not ch.isspace() and ch not in "、。？！?!（）()「」・")
    return [s[i:i + 2] for i in range(len(s) - 1)]


class BM25:
    def __init__(self, docs: list[dict], k1: float = 1.2, b: float = 0.75):
        self.docs = docs
        self.tf = [Counter(grams(d["title"] + " " + d["text"])) for d in docs]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(g for t in self.tf for g in t)
        n = len(docs)
        self.idf = {g: math.log(1 + (n - c + 0.5) / (c + 0.5)) for g, c in df.items()}
        self.k1, self.b = k1, b

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        q = Counter(grams(query))
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for g in q:
                if g in tf:
                    f = tf[g]
                    s += self.idf[g] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scores.append((self.docs[i]["id"], s))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]
