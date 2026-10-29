"""ゴールデンセットの抜き取り（層別）と、漏れ（同じ・ほぼ同じ文がお手本と試験の両方にある）の点検。"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Callable, Sequence


def stratified_sample(rows: Sequence[dict], key: Callable[[dict], tuple], n: int, min_per_stratum: int = 2,
                      seed: int = 0) -> list[dict]:
    """層（key の値）ごとに最低 min_per_stratum 件を取り、残りは層の大きさに比例して配る。

    比例だけだと少ない層（例: 用件が複数の問い合わせ）が 0〜1 件になり、その層の正答率が測れない。
    """
    rng = random.Random(seed)
    strata: dict[tuple, list] = defaultdict(list)
    for r in rows:
        strata[key(r)].append(r)
    for v in strata.values():
        rng.shuffle(v)
    alloc = {k: min(len(v), min_per_stratum) for k, v in strata.items()}
    rest = n - sum(alloc.values())
    if rest < 0:
        raise ValueError("n が層の数 × 最低件数より少ない")
    total = sum(len(v) - alloc[k] for k, v in strata.items())
    # 比例配分（最大剰余法）
    quotas = {k: (len(v) - alloc[k]) * rest / total for k, v in strata.items()} if total else {}
    for k, q in quotas.items():
        alloc[k] += int(q)
    left = n - sum(alloc.values())
    for k in sorted(quotas, key=lambda k: quotas[k] - int(quotas[k]), reverse=True)[:left]:
        alloc[k] += 1
    out = []
    for k in sorted(strata, key=str):
        out += strata[k][: alloc[k]]
    out.sort(key=lambda r: r["id"])
    return out


def char_ngrams(s: str, n: int = 3) -> set:
    s = "".join(s.split())
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def body_of(text: str) -> str:
    """挨拶・署名などの定型を外して、用件の部分だけにする（近さの比較用）。"""
    drop = ("件名", "ソラハ電機 サポートご担当者様", "いつもお世話になっております", "お手数ですが", "よろしくお願いいたします")
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith(drop)]
    return "\n".join(lines)


def leakage(test: Sequence[dict], shots: Sequence[dict], threshold: float = 0.8) -> list[dict]:
    """お手本（few-shot）と試験の組で、用件の文がほぼ同じものを挙げる。"""
    sg = [(s["id"], char_ngrams(body_of(s["text"]))) for s in shots]
    hits = []
    for t in test:
        tg = char_ngrams(body_of(t["text"]))
        for sid, g in sg:
            j = jaccard(tg, g)
            if j >= threshold:
                hits.append({"test": t["id"], "shot": sid, "jaccard": round(j, 3)})
    return hits
