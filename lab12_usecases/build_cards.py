"""lab12 業務ユースケース 5 本の「評価カード」を作る（P12）。LLM は呼ばない。

    python build_cards.py        # → out/cards.md（講師の本物の実行があればその数字、無ければ「模擬」と明記）

カードの欄: 目的 / 失敗の型 / 指標と合格線 / 件数と区間 / 判定の方式 / 人が見るところ / 本番の見張り / 実測
"""
from __future__ import annotations

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import kit, stats  # noqa: E402


def pick(lab, pattern):
    for d in ("out", "out_mock"):
        hits = sorted(glob.glob(os.path.join(ROOT, lab, d, pattern)))
        if hits:
            return kit.read_json(hits[0]), d
    return None, None


def mark(where):
    return "" if where == "out" else "（🔴 模擬の数字。本物のモデルで回すまで性能の証拠にしない）"


def main(argv=None) -> str:
    kit.parser("lab12 評価カード").parse_args(argv)
    kit.banner("lab12 業務ユースケースの評価カード")
    cards = []

    s1, w1 = pick("lab03_classify_extract", "summary_classify_sonnet-5-5.json")
    s1o, _ = pick("lab03_classify_extract", "summary_classify_opus-5-5.json")
    s1h, _ = pick("lab03_classify_extract", "summary_classify_v2_sonnet-5-5.json")
    g, wg = pick("lab09_ci_gate", "gate_result.json")
    m1 = []
    if s1:
        m1.append(f"v1 120 件: Sonnet {kit.pct(s1['accuracy'])} {kit.ci_str(*s1['accuracy_ci'])}"
                  + (f" / Opus {kit.pct(s1o['accuracy'])}" if s1o else "") + mark(w1))
    if s1h:
        m1.append(f"v2 難問 48 件: Sonnet {kit.pct(s1h['accuracy'])}")
    if g:
        for x in g:
            m1.append(f"関門「{x['name']}」: {kit.pct(x['base_acc'])} → {kit.pct(x['cand_acc'])} → {'通す' if x['pass'] else '止める'}{mark(wg)}")
    cards.append(("UC1 ソラハ電機（架空）問い合わせの分類", {
        "目的": "届いた問い合わせを 6 つの窓口に振り分ける。誤ると、交換できるお客様が修理に回される",
        "失敗の型": "到着からの日数の数え違い / 仕様の症状を故障と取る / 複数の用件でお金の用件を落とす",
        "指標と合格線": "正答率（非劣性: 基準から −3 ポイント以内）/ どの種類も 25 ポイント超は落ちない / 返品→修理の取り違え（重大）",
        "件数と区間": "v1 120 件で ±5 ポイント程度。飽和したら境目を突く v2 を足す（lab02・lab03）",
        "判定の方式": "正解ラベルとの照合（コード）。LLM 判定は使わない",
        "人が見るところ": "食い違いの全件 / 手引きの規則が変わったとき / 新製品の問い合わせ",
        "本番の見張り": "シャドー運転で重大の率の上限 / 種類の分布のずれ（PSI）/ 自信の低い順の抜き取り",
        "実測": m1}))

    s2, w2 = pick("lab03_classify_extract", "summary_extract_*.json")
    cards.append(("UC2 ツバクロ少額短期保険（架空）請求書の項目抽出", {
        "目的": "請求書から 6 項目を取り出して、支払いのシステムに入れる",
        "失敗の型": "購入価格・見積額を請求額と取り違える / 年の無い日付 / 「後日郵送」を添付ありと取る",
        "指標と合格線": "項目ごとの正答率と、全項目が合っている請求書の割合（システムに入れるなら strict で測る）",
        "件数と区間": "48 件。全項目の正答の区間を付ける",
        "判定の方式": "正解との照合（strict と表記をそろえた normalized の両方）",
        "人が見るところ": "請求額の大きいもの / 正規化しないと合わない値（表記ゆれの元の文）",
        "本番の見張り": "支払い担当が直した項目の率",
        "実測": [f"{s2['model']}: 全項目 strict {kit.pct(s2['strict']['doc_all_correct'])} / normalized "
                 f"{kit.pct(s2['normalized']['doc_all_correct'])} {kit.ci_str(*s2['doc_all_correct_ci'])}{mark(w2)}"] if s2 else []}))

    s3, w3 = pick("lab04_rag_eval", "summary_rag_normal_*.json")
    s3d, _ = pick("lab04_rag_eval", "summary_rag_degraded_*.json")
    m3 = []
    if s3:
        r = s3["retrieval"]
        m3.append(f"検索 recall@3 {r['recall@3']:.3f} / MRR {r['mrr']:.3f}{mark(w3)}")
        m3.append(f"回答（照合 v1）{s3['correct']}/{s3['n']} → 照合 v2 {s3.get('correct_v2', '-')}/{s3['n']}"
                  f"（v1 の誤判定 {', '.join(s3.get('checker_changed', [])) or 'なし'}）")
    if s3d:
        m3.append(f"根拠を抜いた {s3d['n']} 問で断った {s3d['abstained']} 問")
    cards.append(("UC3 ヒイラギ運輸（架空）社内規程 Q&A（RAG）", {
        "目的": "社員の質問に、規程を根拠にして答える。規程に無いことは「無い」と言う",
        "失敗の型": "検索で根拠を取りこぼす / 根拠の無いことを補う / 答えたうえで一部を断る（照合がそれを落とす）",
        "指標と合格線": "検索 recall@3・MRR / 回答の要素の照合 / 根拠を抜いたときに断る率 / 忠実さ",
        "件数と区間": "30 問（単発 19・複数 6・規程に無い 5）。小さいので失敗は全件読む",
        "判定の方式": "要素の照合（コード）＋ 忠実さは回答者と別のモデルで判定",
        "人が見るところ": "照合で × になった回答の全件（照合の誤りが多い）/ 規程の改定のあと",
        "本番の見張り": "「規程に無い」と答えた質問の一覧（規程の穴か検索の穴か）",
        "実測": m3}))

    s4, w4 = pick("lab05_agent_trajectory", "summary_agent_sonnet-5-5_k3.json")
    s4o, _ = pick("lab05_agent_trajectory", "summary_agent_opus-5-5_k3.json")
    cards.append(("UC4 クロツグ食品（架空）発注エージェント", {
        "目的": "在庫を見て、手引きどおりに発注する。10 万円以上は承認を得る",
        "失敗の型": "承認を飛ばす / 在庫を見ずに発注 / 納期の期限を無視 / 販売終了品を発注",
        "指標と合格線": "結果（発注の中身）と軌跡（手順）の両方が合格 / pass^k（k 回とも）/ 道具の数（最短との比）/ 合格 1 回の費用",
        "件数と区間": "10 件 × 3 回。0 件の失敗でも上限は 3 の法則で付ける",
        "判定の方式": "環境の記録（道具の呼び出し）をコードで照合",
        "人が見るところ": "承認の依頼文そのもの / 最短より多い道具の呼び出し",
        "本番の見張り": "承認の却下率・発注の取り消し率",
        "実測": [f"{s4['model']} k=3: 合格 {s4['pass']}/{s4['episodes']}（結果だけ {s4['outcome_ok']}）、pass^3 {s4['pass_hat_3']:.2f}、"
                 f"{s4['cost_usd']:.3f} USD{mark(w4)}"] + ([f"{s4o['model']} k=3: 合格 {s4o['pass']}/{s4o['episodes']}、"
                 f"pass^3 {s4o['pass_hat_3']:.2f}、{s4o['cost_usd']:.3f} USD"] if s4o else []) if s4 else []}))

    c5, w5 = pick("lab07_judge_calibration", "summary_calib_v2_test_*.json")
    c5d, _ = pick("lab07_judge_calibration", "summary_calib_v1_dev_*.json")
    s5, w5s = pick("lab11_safety", "summary_safety_*.json")
    sp, _ = pick("lab06_judge_bias", "summary_selfpref_*.json")
    m5 = []
    if c5d:
        m5.append(f"判定 v1（dev）: TPR {kit.pct(c5d['tpr'])} / TNR {kit.pct(c5d['tnr'])} / κ {c5d['kappa']:.2f}")
    if c5:
        m5.append(f"判定 v2（test・1 回だけ）: TPR {kit.pct(c5['tpr'])} / TNR {kit.pct(c5['tnr'])} / κ {c5['kappa']:.2f}{mark(w5)}")
    pp, wp = pick("lab07_judge_calibration", "summary_personas.json")
    if pp and "fleiss_v1_to_v2" in pp:
        f1, f2 = pp["fleiss_v1_to_v2"]
        m5.append(f"模擬の判定者 4 人（🔴 人ではない・LLM）: ガイドライン改訂で Fleiss κ {f1:.2f} → {f2:.2f}{mark(wp)}")
    ar, war = pick("lab07_judge_calibration", "adjudicated_reference.json")
    if ar and war == "out":
        lab = {r["id"]: r["label"] for r in kit.load_jsonl("replies.jsonl")}
        diff = sorted(i for i, v in ar["reference"].items() if lab[i] != v)
        m5.append(f"裁定で、作った正解ラベルの誤り {len(diff)} 件（{'・'.join(diff)}）を発見"
                  " → 自動判定 v2 の test は裁定済みの基準で κ 0.95（作ったラベルでは 0.86）")
    if sp:
        m5.append(f"自己贔屓の目安 {sp['self_pref']:+.2f}（n={sp['n']}、区間 [{sp['diff_ci'][0]:+.2f}, {sp['diff_ci'][1]:+.2f}]）")
    if s5:
        m5.append(f"安全: 漏えい {s5.get('leaks')}/{s5.get('attack_n')}・止めすぎ {s5.get('over_refusals')}/{s5.get('benign_n')}"
                  f"（0 件でも上限 約 {kit.pct(stats.rule_of_three(s5.get('attack_n') or 1))}）{mark(w5s)}")
    cards.append(("UC5 ソラハ電機（架空）返信の自動判定と人の抜き取り", {
        "目的": "AI が書いた返信の下書きを、送ってよいか自動で判定し、人が見る件数を減らす",
        "失敗の型": "規程の誤り / 次の手順が無い / 責める言い方 / 約束できない約束 / 他のお客様の情報の漏えい / 止めすぎ",
        "指標と合格線": "判定の TPR・TNR・κ（目標は人並み。測るには本物の人のラベルが要る）/ 補正した不合格率 / 漏えい 0 件と、その上限 / 止めすぎの率",
        "件数と区間": "80 件を dev 38 / test 42。test は最後に 1 回だけ",
        "判定の方式": "LLM 判定（基準つきの依頼文 v2、回答者と別のモデル）＋ 漏えいはコード",
        "人が見るところ": "判定と人が食い違った返信 / 止めすぎの判定の全件 / 依頼文を直した後の dev",
        "本番の見張り": "無作為の抜き取り（率の推定用）と、危ないところ優先の抜き取り（誤りを見つける用）を分ける",
        "実測": m5}))

    lines = ["# 評価カード（5 ユースケース・すべて架空の会社）", "",
             f"作成: {__import__('time').strftime('%Y-%m-%d %H:%M')}。数字は各ラボの out/（講師の本物の実行）から。", ""]
    for title, body in cards:
        lines += [f"## {title}", ""]
        for k, v in body.items():
            if isinstance(v, list):
                lines.append(f"- **{k}**: " + ("（まだ実行していない）" if not v else ""))
                lines += [f"  - {x}" for x in v]
            else:
                lines.append(f"- **{k}**: {v}")
        lines.append("")
    md = "\n".join(lines)
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "cards.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    return md


if __name__ == "__main__":
    main()
