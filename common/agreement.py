"""判定どうしの一致を測る（人と人・人と LLM 判定）。

- cohen_kappa        : 2 者の一致（偶然の一致を差し引く）
- fleiss_kappa       : 3 者以上（同じ人数が全件を付けたとき）
- krippendorff_alpha : 欠けがあっても使える（名義尺度）
- tpr_tnr            : 判定を「人のラベルを正」として、不合格を見つける率 / 合格を合格とする率
- rogan_gladen       : 判定が数えた不合格率を、TPR/TNR で本当の率に直す（Rogan & Gladen 1978）
- landis_koch        : κ の目安の言葉（Landis & Koch 1977）。目安であって合格線ではない
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Hashable, Sequence


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    assert len(a) == len(b) and a
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def fleiss_kappa(ratings: Sequence[Sequence[Hashable]]) -> float:
    """ratings[i] = i 番目の項目に各評価者が付けたラベルの並び（人数は全項目で同じ）。"""
    cats = sorted({r for row in ratings for r in row}, key=str)
    N = len(ratings)
    m = len(ratings[0])
    P_i, totals = [], Counter()
    for row in ratings:
        c = Counter(row)
        totals.update(c)
        P_i.append((sum(v * v for v in c.values()) - m) / (m * (m - 1)))
    P_bar = sum(P_i) / N
    p_j = [totals[k] / (N * m) for k in cats]
    P_e = sum(p * p for p in p_j)
    return 1.0 if P_e == 1 else (P_bar - P_e) / (1 - P_e)


def krippendorff_alpha(units: Sequence[Sequence[Hashable | None]]) -> float:
    """名義尺度の α。units[i] = 項目 i への各評価者のラベル（付けていなければ None）。"""
    coinc: Counter = Counter()
    for row in units:
        vals = [v for v in row if v is not None]
        m = len(vals)
        if m < 2:
            continue
        for i, x in enumerate(vals):
            for j, y in enumerate(vals):
                if i != j:
                    coinc[(x, y)] += 1 / (m - 1)
    n_c: Counter = Counter()
    for (x, _), v in coinc.items():
        n_c[x] += v
    n = sum(n_c.values())
    if n <= 1:
        return float("nan")
    Do = sum(v for (x, y), v in coinc.items() if x != y) / n
    De = sum(n_c[x] * n_c[y] for x in n_c for y in n_c if x != y) / (n * (n - 1))
    return 1.0 if De == 0 else 1 - Do / De


def tpr_tnr(pred: Sequence[str], truth: Sequence[str], positive: str = "fail") -> dict:
    tp = sum(1 for p, t in zip(pred, truth) if t == positive and p == positive)
    fn = sum(1 for p, t in zip(pred, truth) if t == positive and p != positive)
    tn = sum(1 for p, t in zip(pred, truth) if t != positive and p != positive)
    fp = sum(1 for p, t in zip(pred, truth) if t != positive and p == positive)
    return {"tp": tp, "fn": fn, "tn": tn, "fp": fp,
            "tpr": tp / (tp + fn) if tp + fn else float("nan"),
            "tnr": tn / (tn + fp) if tn + fp else float("nan")}


def rogan_gladen(p_obs: float, tpr: float, tnr: float) -> float:
    den = tpr + tnr - 1
    if den <= 0:
        return float("nan")   # 判定がでたらめ以下なら直せない
    return min(1.0, max(0.0, (p_obs + tnr - 1) / den))


def corrected_prevalence_ci(labeled_pred: Sequence[str], labeled_truth: Sequence[str],
                            unlabeled_pred: Sequence[str], positive: str = "fail", B: int = 2000,
                            seed: int = 0) -> dict:
    """人のラベル付き（校正用）とラベル無し（本番）の両方を引き直して、直した不合格率の区間を出す。"""
    rng = random.Random(seed)
    lab = list(zip(labeled_pred, labeled_truth))
    unl = list(unlabeled_pred)
    def est(lab_s, unl_s):
        m = tpr_tnr([p for p, _ in lab_s], [t for _, t in lab_s], positive)
        p_obs = sum(1 for p in unl_s if p == positive) / len(unl_s)
        return rogan_gladen(p_obs, m["tpr"], m["tnr"]), p_obs
    point, p_obs = est(lab, unl)
    vals = []
    for _ in range(B):
        ls = [lab[rng.randrange(len(lab))] for _ in lab]
        us = [unl[rng.randrange(len(unl))] for _ in unl]
        v, _ = est(ls, us)
        if v == v:
            vals.append(v)
    vals.sort()
    lo = vals[int(0.025 * len(vals))] if vals else float("nan")
    hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))] if vals else float("nan")
    return {"observed": p_obs, "corrected": point, "lo": lo, "hi": hi}


def landis_koch(k: float) -> str:
    if k != k:
        return "-"
    if k < 0:
        return "poor (<0)"
    for hi, word in ((0.20, "slight"), (0.40, "fair"), (0.60, "moderate"), (0.80, "substantial")):
        if k <= hi:
            return word
    return "almost perfect"
