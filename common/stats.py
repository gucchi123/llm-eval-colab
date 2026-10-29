"""評価の数字に「誤差の幅」をつけるための小さな統計（標準ライブラリだけ）。

- wilson            : 割合の信頼区間（Wilson 1927）。0% や 100% でも幅が出る
- bootstrap_ci      : 平均などのブートストラップ区間（乱数固定）
- paired_bootstrap  : 同じ問いでの 2 方式の差（対応あり）の区間
- mcnemar_exact     : 同じ問いでの正誤の食い違い（b, c）だけで差を検定する
- paired_permutation: 対応のある差の並べ替え検定
- cluster_se        : 問いが塊（同じ文書・同じ顧客）になっているときの標準誤差（Miller 2024 の勧め）
- n_for_margin      : 割合を ±margin で知るのに要る件数
- n_paired          : 対応ありの 2 方式の差 delta を見つけるのに要る件数（McNemar の近似）
- rule_of_three     : 0 件だったときの上限（95%）は約 3/n
- holm              : 多重比較の補正
- chi2_sf / psi     : 分布のずれ（ドリフト）の検定と PSI
"""
from __future__ import annotations

import math
import random
from statistics import NormalDist
from typing import Callable, Sequence

_N = NormalDist()


def z(conf: float = 0.95) -> float:
    return _N.inv_cdf(0.5 + conf / 2)


def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    zz = z(conf)
    p = k / n
    den = 1 + zz * zz / n
    c = (p + zz * zz / (2 * n)) / den
    h = zz * math.sqrt(p * (1 - p) / n + zz * zz / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_ci(xs: Sequence[float], stat: Callable[[Sequence[float]], float] = mean, B: int = 2000,
                 conf: float = 0.95, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(xs)
    vals = sorted(stat([xs[rng.randrange(n)] for _ in range(n)]) for _ in range(B))
    lo = vals[int((1 - conf) / 2 * B)]
    hi = vals[min(B - 1, int((1 + conf) / 2 * B))]
    return (lo, hi)


def paired_bootstrap(a: Sequence[float], b: Sequence[float], B: int = 4000, conf: float = 0.95,
                     seed: int = 0) -> dict:
    """b − a の平均差と区間。a, b は同じ問いの順に並んだ点数（正誤なら 0/1）。"""
    assert len(a) == len(b) and a, "同じ問いで比べること"
    d = [y - x for x, y in zip(a, b)]
    lo, hi = bootstrap_ci(d, B=B, conf=conf, seed=seed)
    return {"diff": mean(d), "lo": lo, "hi": hi, "n": len(d)}


def _binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def mcnemar_exact(b: int, c: int) -> float:
    """b: a だけ正しい件数、c: b だけ正しい件数。両側の正確な p 値。"""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * _binom_cdf(min(b, c), n))


def discordant(a: Sequence[int], b: Sequence[int]) -> tuple[int, int]:
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    return only_a, only_b


def paired_permutation(a: Sequence[float], b: Sequence[float], B: int = 10000, seed: int = 0) -> float:
    rng = random.Random(seed)
    d = [y - x for x, y in zip(a, b)]
    obs = abs(sum(d))
    hit = 0
    for _ in range(B):
        s = sum(x if rng.random() < 0.5 else -x for x in d)
        if abs(s) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (B + 1)


def cluster_se(xs: Sequence[float], clusters: Sequence[str]) -> float:
    """塊ごとの相関を考えた平均の標準誤差（塊が 1 件ずつなら普通の SE とほぼ同じ）。"""
    n = len(xs)
    m = mean(xs)
    groups: dict[str, float] = {}
    for x, c in zip(xs, clusters):
        groups[c] = groups.get(c, 0.0) + (x - m)
    G = len(groups)
    var = sum(v * v for v in groups.values()) / (n * n)
    if G > 1:
        var *= G / (G - 1)
    return math.sqrt(var)


def naive_se(xs: Sequence[float]) -> float:
    n = len(xs)
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else float("nan")


def n_for_margin(margin: float, p: float = 0.5, conf: float = 0.95) -> int:
    return math.ceil(z(conf) ** 2 * p * (1 - p) / margin ** 2)


def n_paired(delta: float, p_disc: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """McNemar の件数の近似（Connor 1987）。delta: 正答率の差、p_disc: 食い違う問いの割合。"""
    if p_disc <= delta ** 2 or delta <= 0:
        return 10 ** 9
    za = z(1 - alpha)
    zb = _N.inv_cdf(power)
    return math.ceil((za * math.sqrt(p_disc) + zb * math.sqrt(p_disc - delta ** 2)) ** 2 / delta ** 2)


def rule_of_three(n: int) -> float:
    return 3.0 / n if n else 1.0


def holm(pvals: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, stop = {}, False
    for i, (k, p) in enumerate(items):
        if stop or p > alpha / (m - i):
            stop = True
            out[k] = False
        else:
            out[k] = True
    return out


# ---------------------------------------------------------------- ドリフト
def _gammainc_upper_reg(s: float, x: float) -> float:
    """正則化上側不完全ガンマ Q(s, x)（Numerical Recipes の級数と連分数）。"""
    if x <= 0:
        return 1.0
    gln = math.lgamma(s)
    if x < s + 1:
        ap, tot, de = s, 1.0 / s, 1.0 / s
        for _ in range(500):
            ap += 1
            de *= x / ap
            tot += de
            if abs(de) < abs(tot) * 1e-14:
                break
        return 1.0 - tot * math.exp(-x + s * math.log(x) - gln)
    b = x + 1 - s
    c = 1 / 1e-300
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - s)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-14:
            break
    return math.exp(-x + s * math.log(x) - gln) * h


def chi2_sf(x: float, dof: int) -> float:
    return _gammainc_upper_reg(dof / 2, x / 2)


def chi2_homogeneity(counts_a: dict[str, int], counts_b: dict[str, int]) -> tuple[float, int, float]:
    """2 つの期間のカテゴリ分布が同じかの検定。(統計量, 自由度, p)。"""
    cats = sorted(set(counts_a) | set(counts_b))
    na, nb = sum(counts_a.values()), sum(counts_b.values())
    stat = 0.0
    for c in cats:
        tot = counts_a.get(c, 0) + counts_b.get(c, 0)
        for obs, n in ((counts_a.get(c, 0), na), (counts_b.get(c, 0), nb)):
            exp = tot * n / (na + nb)
            if exp > 0:
                stat += (obs - exp) ** 2 / exp
    dof = len(cats) - 1
    return stat, dof, chi2_sf(stat, dof)


def psi(base: dict[str, int], cur: dict[str, int], eps: float = 1e-4) -> float:
    """Population Stability Index。目安: 0.1 未満は小さい、0.25 超は大きい（業界の慣行）。"""
    cats = set(base) | set(cur)
    nb, nc = sum(base.values()), sum(cur.values())
    s = 0.0
    for c in cats:
        pb = max(base.get(c, 0) / nb, eps)
        pc = max(cur.get(c, 0) / nc, eps)
        s += (pc - pb) * math.log(pc / pb)
    return s


def percentile(xs: Sequence[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    i = (len(s) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)
