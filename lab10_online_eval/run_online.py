"""lab10 本番での評価（P10）。LLM は呼ばない。

    python run_online.py

🔴 1〜4 の本番の流れは「模擬」（乱数固定の作りもの。数字は手順の説明用で、性能の証拠ではない）。
   5 の費用と待ち時間だけは、講師が本物のモデルで回したときの台帳（_api_cost_ledger.jsonl）から計算する。

1. シャドー運転: AI の分類を記録だけして、人の分類と週ごとに比べる。重大な食い違いの率に上限を付けて切り替えを決める
2. カナリア: 新しい依頼文を 10% の流量で出す。まず割り当ての比（SRM）を確かめてから、再問い合わせ率を比べる
3. ずれ（ドリフト）: 問い合わせの種類の分布が変わったら、試験セットが本番を代表しなくなる
4. 人が見る抜き取り: 同じ 40 件/週でも、無作為と危ないところ優先で、見つかる誤りの数が違う
5. 費用と待ち時間: 呼び出しごとの p50 / p95、1 件あたりの費用、月の見込み
"""
from __future__ import annotations

import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import kit, llm as L, stats  # noqa: E402

LABELS = ["返品・交換", "修理・故障", "配送", "請求・支払い", "使い方", "会員・解約"]
BASE_MIX = [0.27, 0.12, 0.09, 0.21, 0.21, 0.10]
# 模擬の AI の誤り方: 正解ラベルごとの誤り率と、誤ったときのラベル
AI_ERR = {"返品・交換": (0.04, "修理・故障"), "修理・故障": (0.05, "返品・交換"), "配送": (0.02, "請求・支払い"),
          "請求・支払い": (0.03, "配送"), "使い方": (0.06, "修理・故障"), "会員・解約": (0.01, "使い方")}
CRITICAL = {("返品・交換", "修理・故障")}   # 交換できるお客様を修理に回す（お客様の権利を損なう）


def simulate(seed=20261018, weeks=8, per_week=400):
    rng = random.Random(seed)
    rows = []
    for w in range(1, weeks + 1):
        mix = BASE_MIX[:]
        if w >= 6:   # 新製品の発売で「使い方」が倍に
            mix[4] *= 2
            s = sum(mix)
            mix = [m / s for m in mix]
        for _ in range(per_week):
            t = rng.choices(LABELS, weights=mix)[0]
            err, wrong = AI_ERR[t]
            if w >= 6 and t == "使い方":
                err *= 2.5            # 新製品の問い合わせは試験セットに無い → 誤りが増える
            ai = wrong if rng.random() < err else t
            human = t if rng.random() > 0.02 else rng.choice(LABELS)
            conf = rng.uniform(0.55, 0.8) if ai != t else rng.uniform(0.7, 0.99)
            rows.append({"week": w, "truth": t, "ai": ai, "human": human, "conf": conf,
                         "arm": "canary" if rng.random() < 0.1 else "control"})
    return rows


def main(argv=None) -> dict:
    kit.parser("lab10 本番での評価").parse_args(argv)
    kit.banner("lab10 本番での評価（1〜4 は模擬、5 は本物の台帳）")
    rows = simulate()
    res = {}

    print("\n1. シャドー運転（模擬・1〜4 週）: AI の分類を出さずに記録し、人の分類と比べる")
    tbl = []
    for w in range(1, 5):
        sub = [r for r in rows if r["week"] == w]
        agree = sum(r["ai"] == r["human"] for r in sub)
        crit = sum((r["human"], r["ai"]) in CRITICAL for r in sub)
        lo, hi = stats.wilson(crit, len(sub))
        tbl.append([f"W{w}", len(sub), kit.pct(agree / len(sub)), crit, f"{100 * hi:.2f}%"])
    print(kit.table(tbl, ["週", "件数", "人との一致", "重大な食い違い", "重大の率の上限(95%)"]))
    sub = [r for r in rows if r["week"] <= 4]
    crit = sum((r["human"], r["ai"]) in CRITICAL for r in sub)
    lo, hi = stats.wilson(crit, len(sub))
    target = 0.002
    need = stats.rule_of_three(1) / target
    print(f"   4 週合計: 重大 {crit}/{len(sub)}、率の上限 {100 * hi:.2f}%。決まり「重大の率の上限 < {100 * target:.1f}%」→ "
          f"{'満たす' if hi < target else '満たさない'}（重大 0 件でも、0.2% 未満と言うには {int(need)} 件以上が要る）")
    print("   🔴 人のラベルにも誤りがある（模擬では 2%）。食い違いは「AI の誤り」とは限らない → 食い違いは人が読み直す")
    res["shadow"] = {"critical": crit, "n": len(sub), "upper": hi}

    print("\n2. カナリア（模擬・5〜6 週）: 新しい依頼文を流量の 10% に出す")
    can = [r for r in rows if r["week"] in (5, 6)]
    nc = sum(r["arm"] == "canary" for r in can)
    nt = len(can) - nc
    exp_c = len(can) * 0.1
    chi = (nc - exp_c) ** 2 / exp_c + (nt - (len(can) - exp_c)) ** 2 / (len(can) - exp_c)
    p_srm = stats.chi2_sf(chi, 1)
    print(f"   割り当て: カナリア {nc} / 対照 {nt}（期待 10%）→ SRM の検定 p={p_srm:.3f}"
          f" {'（比は正常。先へ進む）' if p_srm > 0.001 else '（比がおかしい。結果を読まずに配分の仕組みを直す）'}")
    rng = random.Random(7)
    rec = {"canary": [], "control": []}
    for r in can:
        base_p = 0.08 + (0.10 if r["ai"] != r["truth"] else 0)
        if r["arm"] == "canary":
            base_p -= 0.01
        rec[r["arm"]].append(1 if rng.random() < base_p else 0)
    a, b = rec["control"], rec["canary"]
    pa, pb = sum(a) / len(a), sum(b) / len(b)
    se = (pa * (1 - pa) / len(a) + pb * (1 - pb) / len(b)) ** 0.5
    print(f"   再問い合わせ率: 対照 {kit.pct(pa)} / カナリア {kit.pct(pb)}、差 {100 * (pb - pa):+.1f} ポイント、"
          f"95%区間 [{100 * (pb - pa - 1.96 * se):+.1f}, {100 * (pb - pa + 1.96 * se):+.1f}]（n={len(b)} では差は言えない）")
    res["canary"] = {"n_canary": nc, "n_control": nt, "srm_p": p_srm, "diff": pb - pa, "se": se}

    print("\n3. ずれ（模擬）: 1〜4 週と 6 週の種類の分布")
    c1 = Counter(r["truth"] for r in rows if r["week"] <= 4)
    c6 = Counter(r["truth"] for r in rows if r["week"] == 6)
    stat, dof, p = stats.chi2_homogeneity(c1, c6)
    ps = stats.psi(c1, c6)
    acc1 = sum(r["ai"] == r["truth"] for r in rows if r["week"] <= 4) / sum(1 for r in rows if r["week"] <= 4)
    acc6 = sum(r["ai"] == r["truth"] for r in rows if r["week"] == 6) / sum(1 for r in rows if r["week"] == 6)
    print(f"   χ²={stat:.1f}（自由度 {dof}）p={p:.2g}、PSI={ps:.3f}。「使い方」{kit.pct(c1['使い方'] / sum(c1.values()))} → "
          f"{kit.pct(c6['使い方'] / sum(c6.values()))}")
    print(f"   AI の正答（正解は模擬で既知）: 1〜4 週 {kit.pct(acc1)} → 6 週 {kit.pct(acc6)}。"
          "試験セットに新製品の問い合わせを足し、版を上げる（lab02 のデータカードの更新）")
    res["drift"] = {"chi2": stat, "p": p, "psi": ps, "acc_before": acc1, "acc_after": acc6}

    print("\n4. 人が見る抜き取り（模擬・7 週、40 件/週）: 見つかる AI の誤りの数")
    wk = [r for r in rows if r["week"] == 7]
    errs = sum(r["ai"] != r["truth"] for r in wk)
    rng = random.Random(3)
    rnd = rng.sample(wk, 40)
    risk = sorted(wk, key=lambda r: (r["conf"], r["ai"] not in ("返品・交換", "修理・故障", "請求・支払い")))[:40]
    f_r = sum(r["ai"] != r["truth"] for r in rnd)
    f_k = sum(r["ai"] != r["truth"] for r in risk)
    print(f"   この週の AI の誤り {errs}/{len(wk)} 件。無作為 40 件で見つかる {f_r} 件 / 自信の低い順 40 件で見つかる {f_k} 件")
    print("   🔴 危ないところ優先の抜き取りは、全体の誤り率の推定には使えない（偏っている）。推定には無作為の抜き取りを別に残す")
    res["review"] = {"errors": errs, "random_found": f_r, "risk_found": f_k}

    print("\n5. 費用と待ち時間（本物: 講師の台帳）")
    led = [e for e in L.read_ledger() if not e.get("cached") and e.get("tag", "").count("/") >= 1]
    if not led:
        print("   台帳がありません（本物のモデルで回すと出ます）")
    else:
        groups = {}
        for e in led:
            g = "/".join(e["tag"].split("/")[:2]) + " · " + ("opus" if "opus" in e["model"] else "sonnet")
            groups.setdefault(g, []).append(e)
        tbl = []
        for g, es in sorted(groups.items()):
            secs = [e["seconds"] for e in es]
            tbl.append([g, len(es), f"{stats.percentile(secs, .5):.1f}", f"{stats.percentile(secs, .95):.1f}",
                        f"{sum(e['cost_usd'] for e in es) / len(es):.4f}", f"{sum(e['out'] for e in es) / len(es):.0f}"])
        print(kit.table(tbl, ["ラボ · モデル", "呼び出し", "p50 秒", "p95 秒", "USD/回", "出力トークン/回"]))
        for m in ("opus", "sonnet"):
            es = [e for e in led if e["tag"].startswith("lab03/classify") and m in e["model"] and "/v2/" not in e["tag"]]
            if es:
                per = sum(e["cost_usd"] for e in es) / len(es)
                print(f"   分類 1 件 {m}: {per:.4f} USD → 月 1,600 件で {per * 1600:.2f} USD（v1 では正答はどちらも 120/120）")
        res["latency_cost"] = tbl
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    kit.write_json(os.path.join(out, "summary_online.json"), res)
    return res


if __name__ == "__main__":
    main()
