"""タスク別の指標（分類・抽出・検索）。"""
from __future__ import annotations

import math
from collections import Counter
from typing import Hashable, Sequence


# ---------------------------------------------------------------- 分類
def confusion(truth: Sequence[Hashable], pred: Sequence[Hashable], classes: Sequence[Hashable]) -> dict:
    m = {t: {p: 0 for p in list(classes) + ["(無効)"]} for t in classes}
    for t, p in zip(truth, pred):
        m[t][p if p in classes else "(無効)"] += 1
    return m


def per_class(truth, pred, classes) -> dict:
    out = {}
    for c in classes:
        tp = sum(1 for t, p in zip(truth, pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(truth, pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(truth, pred) if t == c and p != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[c] = {"support": tp + fn, "precision": prec, "recall": rec, "f1": f1}
    return out


def classification_report(truth, pred, classes) -> dict:
    pc = per_class(truth, pred, classes)
    n = len(truth)
    acc = sum(1 for t, p in zip(truth, pred) if t == p) / n if n else 0.0
    macro = sum(v["f1"] for v in pc.values()) / len(classes)
    tp = sum(1 for t, p in zip(truth, pred) if t == p)
    micro = tp / n if n else 0.0     # 単一ラベルでは micro-F1 = 正答率
    return {"n": n, "accuracy": acc, "macro_f1": macro, "micro_f1": micro, "per_class": pc}


def ece(confs: Sequence[float], correct: Sequence[int], bins: int = 5) -> tuple[float, list[dict]]:
    """Expected Calibration Error（Guo et al. 2017）。confs は 0〜1。"""
    n = len(confs)
    table, total = [], 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confs) if (lo < c <= hi) or (b == 0 and c == 0)]
        if not idx:
            table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": 0, "conf": None, "acc": None})
            continue
        conf = sum(confs[i] for i in idx) / len(idx)
        acc = sum(correct[i] for i in idx) / len(idx)
        total += len(idx) / n * abs(acc - conf)
        table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(idx), "conf": conf, "acc": acc})
    return total, table


# ---------------------------------------------------------------- 抽出
def field_scores(golds: Sequence[dict], preds: Sequence[dict], fields: Sequence[str], norm=None) -> dict:
    """項目ごとの正答率と、全項目が合っている文書の割合。norm(field, value) で揃えてから比べる。"""
    norm = norm or (lambda f, v: v)
    per = {f: 0 for f in fields}
    all_ok = 0
    for g, p in zip(golds, preds):
        ok_doc = True
        for f in fields:
            ok = norm(f, g.get(f)) == norm(f, (p or {}).get(f))
            per[f] += ok
            ok_doc &= ok
        all_ok += ok_doc
    n = len(golds)
    return {"n": n, "per_field": {f: per[f] / n for f in fields}, "doc_all_correct": all_ok / n}


# ---------------------------------------------------------------- 検索
def recall_at_k(ranked: Sequence[str], relevant: set, k: int) -> float:
    if not relevant:
        return float("nan")
    return len(set(ranked[:k]) & relevant) / len(relevant)


def mrr(ranked: Sequence[str], relevant: set) -> float:
    for i, d in enumerate(ranked, 1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: set, k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(ranked[:k], 1) if d in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal if ideal else float("nan")


def label_counts(xs) -> dict:
    return dict(Counter(xs))


# ---------------------------------------------------------------- 何度か試すエージェント
def pass_at_k(n: int, c: int, k: int) -> float:
    """n 回試して c 回成功。k 回のうち少なくとも 1 回成功する確率の不偏推定（Chen et al. 2021 式 1）。"""
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """k 回とも成功する確率（tau-bench の pass^k）。C(c,k)/C(n,k)。"""
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)
