"""lab08 差は本物か（P8）。LLM は呼ばない。ほかのラボの実行結果（out/、無ければ out_mock/）を読んで計算する。

    python run_stats.py

1. 0 件・全問正解の読み方: 120/120 でも誤り率の上限は約 2.5%（Wilson / 3 の法則）
2. 対応のある比較: 同じ問いで基準と候補を比べる（McNemar・対のブートストラップ・並べ替え検定）
3. 塊の標準誤差: 似た問いが固まっていると、素朴な SE は小さすぎる（Miller 2024 §2.2）
4. 必要な件数: 差 3 / 5 / 10 ポイントを、検出力 80% で見つけるには何問要るか
5. 多重比較: 種類ごとに 6 回検定したら、Holm で補正する
6. 同じ判定を順番だけ変えて 2 回: 判定そのものの揺れ（lab06）
"""
from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import kit, stats  # noqa: E402


def find(lab, name):
    for d in ("out", "out_mock"):
        p = os.path.join(ROOT, lab, d, name)
        if os.path.exists(p):
            return p, d
    return None, None


def synthetic(seed=0, n=48):
    """他のラボを回していないとき用の、決まった乱数の組（模擬）。"""
    rng = random.Random(seed)
    scen = [f"S{i % 6}" for i in range(n)]
    base = [1] * n
    cand = [0 if (s in ("S4", "S5") and rng.random() < 0.6) else 1 for s in scen]
    return [{"id": f"X{i}", "correct": b, "scenario": s} for i, (b, s) in enumerate(zip(base, scen))], \
           [{"id": f"X{i}", "correct": c, "scenario": s} for i, (c, s) in enumerate(zip(cand, scen))]


def main(argv=None) -> dict:
    kit.parser("lab08 統計").parse_args(argv)
    kit.banner("lab08 差は本物か（LLM なし）")
    res = {}

    # 1
    print("\n1. 全問正解・0 件の読み方")
    for k, n, what in [(120, 120, "分類 v1（Opus / Sonnet とも）"), (48, 48, "分類 v2 難問（Sonnet）"), (0, 12, "漏えい 0/12（lab11）")]:
        lo, hi = stats.wilson(k, n)
        err_hi = 1 - lo if k == n else hi
        print(f"   {what}: {k}/{n} → 95%区間 {kit.ci_str(lo, hi)}、{'誤り' if k == n else '起きる'}率の上限 {kit.pct(err_hi)}"
              f"（3 の法則 {kit.pct(stats.rule_of_three(n))}）")

    # 2
    pb, where_b = find("lab03_classify_extract", "runs_classify_v2_sonnet-5-5.jsonl")
    pc, where_c = find("lab09_ci_gate", "runs_candidate_v2_sonnet-5-5.jsonl")
    if pb and pc:
        base, cand = kit.read_jsonl(pb), kit.read_jsonl(pc)
        src = f"本物の実行（{where_b}・{where_c}）"
    else:
        pb, _ = find("lab03_classify_extract", "runs_classify_v2_opus-5-5.jsonl")
        pc, _ = find("lab09_ci_gate", "runs_candidate_v2_opus-5-5.jsonl")
        if pb and pc:
            base, cand = kit.read_jsonl(pb), kit.read_jsonl(pc)
            src = "模擬の出力（out_mock）"
        else:
            base, cand = synthetic()
            src = "決まった乱数の組（模擬）"
    cb = {r["id"]: r for r in cand}
    ids = [r["id"] for r in base if r["id"] in cb]
    bm = {r["id"]: r for r in base}
    a = [bm[i]["correct"] for i in ids]
    b = [cb[i]["correct"] for i in ids]
    ob, oc = stats.discordant(a, b)
    pbs = stats.paired_bootstrap(a, b, seed=0)
    p_mc = stats.mcnemar_exact(ob, oc)
    p_perm = stats.paired_permutation(a, b, B=5000, seed=0)
    print(f"\n2. 対応のある比較: 基準（全文の手引き）vs 候補（短くした依頼文）、{src}、n={len(ids)}")
    print(f"   正答 {sum(a)} → {sum(b)}、食い違い: 基準だけ正解 {ob} / 候補だけ正解 {oc}")
    print(f"   差 {pbs['diff']:+.3f}、対のブートストラップ 95%区間 [{pbs['lo']:+.3f}, {pbs['hi']:+.3f}]、"
          f"McNemar p={p_mc:.2g}、並べ替え p={p_perm:.2g}")
    # 対にしないで比べた場合（2 つの独立な割合として）
    la, ha = stats.wilson(sum(a), len(a))
    lb, hb = stats.wilson(sum(b), len(b))
    print(f"   対にしないで区間だけ並べると: 基準 {kit.ci_str(la, ha)} / 候補 {kit.ci_str(lb, hb)}"
          f"（重なるかどうかで判断すると、差を見落としやすい）")
    res["paired"] = {"n": len(ids), "only_base": ob, "only_cand": oc, **pbs, "mcnemar_p": p_mc, "perm_p": p_perm, "source": src}

    # 3
    scen = [bm[i]["scenario"] for i in ids]
    naive = stats.naive_se(b)
    clus = stats.cluster_se(b, scen)
    print(f"\n3. 塊の標準誤差（候補の正答、{len(set(scen))} 種類の塊）: 素朴な SE {naive:.3f} / 塊の SE {clus:.3f}（{clus / naive:.2f} 倍）")
    res["cluster"] = {"naive": naive, "clustered": clus}

    # 4
    pd = max((ob + oc) / len(ids), 0.05)
    print(f"\n4. 必要な件数（対あり・α=0.05 両側・検出力 80%、食い違う問いの割合 {pd:.2f} と仮定）")
    rows = [[f"{int(d * 100)} ポイント", stats.n_paired(d, max(pd, d * 1.5))] for d in (0.03, 0.05, 0.10, 0.20)]
    print(kit.table(rows, ["見つけたい差", "必要な問いの数"]))
    print(f"   参考: 割合を ±5 ポイントで知るには {stats.n_for_margin(0.05)} 件、±3 ポイントなら {stats.n_for_margin(0.03)} 件（p=0.5）")
    res["n_paired"] = rows

    # 5
    pv = {}
    for s in sorted(set(scen)):
        sid = [i for i in ids if bm[i]["scenario"] == s]
        x, y = stats.discordant([bm[i]["correct"] for i in sid], [cb[i]["correct"] for i in sid])
        pv[s] = stats.mcnemar_exact(x, y)
    keep = stats.holm(pv)
    print("\n5. 種類ごとの検定（McNemar）と Holm の補正:")
    for s, p in sorted(pv.items(), key=lambda kv: kv[1]):
        print(f"   {s:14s} p={p:.3f}  補正前 {'有意' if p < 0.05 else '-'} / Holm {'有意' if keep[s] else '-'}")
    res["holm"] = {s: {"p": pv[s], "holm": keep[s]} for s in pv}

    # 6
    pn, w = find("lab06_judge_bias", "runs_bias_naive_sonnet-5-5.jsonl")
    pcar, _ = find("lab06_judge_bias", "runs_bias_careful_sonnet-5-5.jsonl")
    if pn and pcar:
        for name, path in (("素朴な依頼文", pn), ("基準つきの依頼文", pcar)):
            rr = [r for r in kit.read_jsonl(path) if r["kind"] == "equal"]
            c = sum(r["consistent"] for r in rr)
            print(f"\n6. 判定の揺れ（{name}・同じ質の {len(rr)} 組を順番だけ変えて 2 回）: 結論が同じ {c}/{len(rr)}"
                  f" 95%区間 {kit.ci_str(*stats.wilson(c, len(rr)))}（{w}）")
            res.setdefault("judge_consistency", {})[name] = [c, len(rr)]
    else:
        print("\n6. 判定の揺れ: lab06 の出力がまだありません（lab06 の run_bias.py を回すと出ます）")
    # 7. 2 つの検定が食い違うとき（短い依頼文の下での Sonnet と Opus）
    ps, _ = find("lab09_ci_gate", "runs_candidate_v2_sonnet-5-5.jsonl")
    po, wo = find("lab09_ci_gate", "runs_candidate_v2_opus-5-5.jsonl")
    if ps and po and wo == "out":
        sa = {r["id"]: r["correct"] for r in kit.read_jsonl(ps)}
        oa = {r["id"]: r["correct"] for r in kit.read_jsonl(po)}
        ii = sorted(sa)
        x, y = [sa[i] for i in ii], [oa[i] for i in ii]
        s_only, o_only = stats.discordant(x, y)
        bs = stats.paired_bootstrap(x, y, seed=0)
        pm = stats.mcnemar_exact(s_only, o_only)
        print(f"\n7. 短い依頼文の下で Sonnet {sum(x)}/48 と Opus {sum(y)}/48（同じ 48 問）: Sonnet だけ正解 {s_only} / Opus だけ正解 {o_only}")
        print(f"   McNemar（正確）p={pm:.3f}（5% では言えない）/ 対のブートストラップ 95%区間 [{bs['lo']:+.3f}, {bs['hi']:+.3f}]（0 を含まない）")
        print("   → 件数が少ないと、方法によって結論が割れる。事前に方法を 1 つ決めておき、割れたら件数を増やす")
        res["sonnet_vs_opus_trimmed"] = {"sonnet_only": s_only, "opus_only": o_only, "mcnemar_p": pm, "boot": bs}
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    kit.write_json(os.path.join(out, "summary_stats.json"), res)
    return res


if __name__ == "__main__":
    main()
