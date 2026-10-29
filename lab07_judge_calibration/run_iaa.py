"""lab07-2 評価者どうしの一致（inter-annotator agreement の計算練習。評価者は模擬）。LLM は呼ばない。

    python run_iaa.py

🔴 評価者 A・B・C は「模擬」です（data/gen/replies.py の ANNOTATOR_NOISE のくせと乱数で作った）。
本物の人のラベルではありません。計算の手順と、食い違いの読み方を練習するためのもの。
lab07-1 を本物のモデルで回してあれば（out/runs_calib_v2_*.jsonl）、その判定を 4 人目として並べます。

見るところ
- 2 人ずつの κ、3 人の Fleiss κ、Krippendorff α
- 食い違いが「どの欠陥の種類」に集まるか → 基準の書き方が曖昧なところ（ここを直すのが先）
- LLM 判定と各評価者の κ が、評価者どうしの κ と同じくらいか（本番で「人並み」を確かめるには本物の人のラベルが要る）
"""
from __future__ import annotations

import glob
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import agreement as A, kit  # noqa: E402


def main(argv=None) -> dict:
    kit.parser("lab07 評価者どうしの一致").parse_args(argv)
    kit.banner("lab07-2 評価者どうしの一致（評価者は模擬。人ではない）")
    reps = kit.load_jsonl("replies.jsonl")
    raters = ["A", "B", "C"]
    lab = {r: [x["annotators"][r] for x in reps] for r in raters}
    rows = []
    for a, b in itertools.combinations(raters, 2):
        k = A.cohen_kappa(lab[a], lab[b])
        agree = sum(x == y for x, y in zip(lab[a], lab[b])) / len(reps)
        rows.append([f"{a}-{b}", kit.pct(agree), f"{k:.3f}", A.landis_koch(k)])
    print(kit.table(rows, ["組", "一致", "Cohen κ", "目安"]))
    fk = A.fleiss_kappa([[x["annotators"][r] for r in raters] for x in reps])
    ka = A.krippendorff_alpha([[x["annotators"][r] for r in raters] for x in reps])
    print(f"\n3 人: Fleiss κ = {fk:.3f} / Krippendorff α = {ka:.3f}")
    # 欠けがある場合の α（C が半分しか付けていない、という想定）
    ka_missing = A.krippendorff_alpha([[x["annotators"]["A"], x["annotators"]["B"], x["annotators"]["C"] if i % 2 else None]
                                       for i, x in enumerate(reps)])
    print(f"   C が半分しか付けていない場合の α = {ka_missing:.3f}（κ では計算できない形でも α は出せる）")
    print("\n食い違い（3 人がそろわなかった返信）の欠陥の種類:")
    dis = {}
    for x in reps:
        if len({x["annotators"][r] for r in raters}) > 1:
            dis[x["defect"] or "(欠陥なし)"] = dis.get(x["defect"] or "(欠陥なし)", 0) + 1
    for k, v in sorted(dis.items(), key=lambda kv: -kv[1]):
        print(f"   {k:14s} {v} 件")
    # 正解（作った側のラベル）と各評価者
    print("\n作った側のラベルと各評価者: " + " / ".join(
        f"{r} κ={A.cohen_kappa(lab[r], [x['label'] for x in reps]):.3f}" for r in raters))
    res = {"pairwise": rows, "fleiss": fk, "alpha": ka, "alpha_missing": ka_missing, "disagreements": dis}
    # LLM 判定を 4 人目に
    files = sorted(glob.glob(os.path.join(HERE, "out", "runs_calib_v2_*_sonnet-5-5*.jsonl")))
    llm = {}
    for f in files:
        for r in kit.read_jsonl(f):
            llm[r["id"]] = r["judge"]
    if len(llm) >= 40:
        ids = [x["id"] for x in reps if x["id"] in llm]
        sub = {x["id"]: x for x in reps}
        print(f"\nLLM 判定（Sonnet 5.5・依頼文 v2、本物の実行の記録 {len(ids)} 件）と各評価者:")
        for r in raters:
            k = A.cohen_kappa([llm[i] for i in ids], [sub[i]["annotators"][r] for i in ids])
            print(f"   LLM-{r} κ = {k:.3f}")
        res["llm_vs"] = {r: A.cohen_kappa([llm[i] for i in ids], [sub[i]["annotators"][r] for i in ids]) for r in raters}
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    kit.write_json(os.path.join(HERE, "out", "summary_iaa.json"), res)
    return res


if __name__ == "__main__":
    main()
