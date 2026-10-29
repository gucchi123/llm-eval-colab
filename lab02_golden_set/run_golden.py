"""lab02 ゴールデンセットを作る（P2）。LLM は使わない。

    python run_golden.py            # 抜き取りの再現・分布・重み・件数と幅・漏れ・データカード

見るところ
1. 本番の分布（600 件）と、層別に抜き取った 120 件の分布は違う（少ない層を厚めに取ったから）
   → 全体の正答率を言うときは、層の重みで戻す（lab03 の「重み付き正答率」）
2. 120 件で言える幅: 正答率 90% なら Wilson の 95% 区間は約 ±5 ポイント
3. お手本（few-shot）と試験がほぼ同じ文になっていないか（漏れ）。型から作った文は似やすい
"""
from __future__ import annotations

import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import kit, stats  # noqa: E402
from common.sampling import body_of, char_ngrams, jaccard, leakage, stratified_sample  # noqa: E402

LABELS = ["返品・交換", "修理・故障", "配送", "請求・支払い", "使い方", "会員・解約"]


def stratum(r):
    return (r["label"], r["difficulty"])


def strata_weights(pool, golden) -> dict:
    """層ごとの重み = 本番での割合 / 試験での割合。"""
    cp, cg = Counter(map(stratum, pool)), Counter(map(stratum, golden))
    return {f"{k[0]}|{k[1]}": (cp[k] / len(pool)) / (cg[k] / len(golden)) for k in cg}


def near_dup_clusters(rows, threshold=0.8) -> int:
    """用件の文がほぼ同じものを 1 つの塊とみなしたときの塊の数（実効の件数の目安）。"""
    grams = [char_ngrams(body_of(r["text"])) for r in rows]
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if jaccard(grams[i], grams[j]) >= threshold:
                parent[find(i)] = find(j)
    return len({find(i) for i in range(len(rows))})


def main(argv=None) -> dict:
    p = kit.parser("lab02 ゴールデンセット")
    args = p.parse_args(argv)
    kit.banner("lab02 ゴールデンセット（LLM なし）")
    pool = kit.load_jsonl("inquiries_pool.jsonl")
    golden = kit.load_jsonl("golden_inquiries.jsonl")
    shots = kit.load_jsonl("fewshot_inquiries.jsonl")

    # 1. 再現: 同じ seed で抜き直すと同じ 120 件になるか
    again = stratified_sample(pool, key=stratum, n=120, min_per_stratum=3, seed=7)
    same = [r["id"] for r in again] == [r["id"] for r in golden]
    print(f"\n1. 抜き取りの再現（seed=7 で抜き直す）: {'同じ 120 件' if same else '違う！'}")

    # 2. 分布
    print("\n2. ラベルの分布（本番 600 件 vs 試験 120 件）")
    cp, cg = Counter(r["label"] for r in pool), Counter(r["label"] for r in golden)
    rows = [[lab, cp[lab], kit.pct(cp[lab] / len(pool)), cg[lab], kit.pct(cg[lab] / len(golden))] for lab in LABELS]
    print(kit.table(rows, ["ラベル", "本番", "割合", "試験", "割合"]))
    dp, dg = Counter(r["difficulty"] for r in pool), Counter(r["difficulty"] for r in golden)
    print("   難しさ: " + " / ".join(f"{d} 本番 {kit.pct(dp[d] / len(pool))} → 試験 {kit.pct(dg[d] / len(golden))}"
                                    for d in ("easy", "rule", "multi")))
    w = strata_weights(pool, golden)
    print(f"   層の数 {len(w)}、重みの範囲 {min(w.values()):.2f}〜{max(w.values()):.2f}（lab03 で全体の正答率を本番の割合に戻すのに使う）")

    # 3. 件数と幅
    print("\n3. 件数と 95% 区間の幅（正答率 90% のとき）")
    rows = []
    for n in (30, 60, 120, 300, 1000):
        lo, hi = stats.wilson(round(0.9 * n), n)
        rows.append([n, kit.ci_str(lo, hi), f"±{100 * (hi - lo) / 2:.1f}"])
    print(kit.table(rows, ["件数", "区間", "半幅(ポイント)"]))
    print(f"   ±3 ポイントで知りたいなら（p=0.9）: {stats.n_for_margin(0.03, 0.9)} 件 / （p=0.5）: {stats.n_for_margin(0.03, 0.5)} 件")

    # 4. 漏れと重なり
    hits = leakage(golden, shots, threshold=0.8)
    leaked = sorted({h["test"] for h in hits})
    print(f"\n4. 漏れ: お手本 {len(shots)} 件と、用件がほぼ同じ（3 文字 Jaccard ≥ 0.8）試験の問い合わせ: {len(leaked)} 件")
    for h in hits[:5]:
        print(f"   {h['test']} ≈ {h['shot']} (J={h['jaccard']})")
    clusters = near_dup_clusters(golden)
    print(f"   試験 120 件のうち、用件がほぼ同じものをまとめると {clusters} 塊（似た問いが多いほど、実効の件数は 120 より少ない）")

    # 5. データカード
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    man = kit.load_json("MANIFEST.json")
    card = [
        "# データカード: ソラハ電機 問い合わせ分類 ゴールデンセット v1（架空）", "",
        "- 目的: 問い合わせ分類（6 ラベル）の正答率と、規則の当て方の誤りを測る",
        "- 元: 本番の問い合わせ 600 件（架空、data/make_data.py で生成、seed 20261018）",
        "- 抜き取り: ラベル × 難しさ（easy / rule / multi）の層ごとに最低 3 件、残りを比例配分。120 件（seed 7）",
        f"- 正解: 分類の手引き（guide_inquiries.md）の規則をコードで当てたもの。sha256 {man['sha256']['golden_inquiries.jsonl'][:12]}…",
        f"- 層の重み: {min(w.values()):.2f}〜{max(w.values()):.2f}（全体を言うときは重みで戻す）",
        f"- 漏れ: お手本 12 件とほぼ同じ文が試験に {len(leaked)} 件 → お手本は試験と重ならないものに差し替えてから使う",
        f"- 似た文の塊: {clusters} 塊 / 120 件 → 標準誤差は塊で計算する（lab08）",
        "- 既知の限界: 文は型から作っているので、本物の問い合わせより言い回しの幅が狭い。誤字・方言・長文の脱線は無い",
        "- 更新の決まり: 正解を直したら版を上げ、前の版の結果と混ぜない",
    ]
    with open(os.path.join(out, "dataset_card.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(card) + "\n")
    summary = {"reproducible": same, "label_pool": dict(cp), "label_golden": dict(cg), "weights": w,
               "leaked_tests": leaked, "clusters": clusters}
    kit.write_json(os.path.join(out, "summary.json"), summary)
    print("\n5. データカード → out/dataset_card.md")
    return summary


if __name__ == "__main__":
    main()
