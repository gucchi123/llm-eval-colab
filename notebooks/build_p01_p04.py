"""P1〜P4 のノートブック。部品は _nbkit.py、全体は build_notebooks.py。"""
from _nbkit import C, M, nb

BOOKS = {}

BOOKS["p01_providers.ipynb"] = nb(
    "P1 三つの呼び先 ― 模擬・再生・本物",
    "同じコードを、模擬（mock）・講師の記録の再生（replay）・本物の API（anthropic）で動かし分けます。"
    "題材は P3 で詳しく見る、問い合わせ分類（ソラハ電機・6 ラベル）です。", [
    (M, "## 1. 模擬（mock）で 6 件を分類する\nキーも記録も要りません。決まった筋書きで答えるので、数字は性能の証拠になりません。"),
    (C, '''from common import kit, llm as L
rc = lab("run_classify", "lab03_classify_extract")
golden = kit.load_jsonl("golden_inquiries.jsonl")
args = kit.parser("demo").parse_args(["--provider", "mock"])
with L.mock_handler(rc.mock_for(golden)):
    runs = [rc.classify_one(r, args) for r in golden[:6]]
for x in runs:
    print(x["id"], f'{x["label"]:<8}', "→", f'{x["pred"]:<8}', "○" if x["correct"] else "×")'''),
    (M, "## 2. 講師の記録を再生（replay）して、同じ 6 件を分類する\n本物の Opus 5.5 の応答を `.cache/llm/` から返します。費用 0、待ち時間と費用は元の実行の値です。"),
    (C, '''args = kit.parser("demo").parse_args(["--provider", "replay" if PROVIDER == "mock" else PROVIDER,
                                       "--model", "claude-opus-5-5"])
with safe():
    runs = [rc.classify_one(r, args) for r in golden[:6]]
    for x in runs:
        print(x["id"], f'{x["label"]:<8}', "→", f'{x["pred"]:<8}', "○" if x["correct"] else "×",
              f'元の費用 {x["cost_usd"]:.4f} USD / {x["seconds"]:.1f} 秒 / 記録から {bool(x["cached"])}')'''),
    (M, "## 3. 120 件を 2 つのモデルで再生し、RESULTS.md の数字と比べる\nキー無しでも、講師が API で回したときと同じ正答数と費用が出ます。"),
    (C, '''with safe():
    for model in ("claude-sonnet-5-5", "claude-opus-5-5"):
        a = kit.parser("demo").parse_args(["--provider", "replay" if PROVIDER == "mock" else PROVIDER, "--model", model])
        runs = [rc.classify_one(r, a) for r in golden]
        ok = sum(x["correct"] for x in runs)
        print(f"{model:<18} 正答 {ok}/{len(runs)}  費用 {sum(x['cost_usd'] for x in runs):.4f} USD")
print("RESULTS.md: Sonnet 120/120・0.37 USD / Opus 120/120・0.83 USD")'''),
])

# ---------------------------------------------------------------- P2
BOOKS["p02_golden_set.ipynb"] = nb(
    "P2 ゴールデンセットを作る",
    "ソラハ電機の問い合わせ（本番 600 件・架空）から、試験に使う 120 件を層別に抜き取り、"
    "層の重み・件数と区間の幅・お手本からの漏れ・似た文の塊・データカードまでを見ます。LLM は使いません。", [
    (M, "## 1. 層別の抜き取り ― 少ない層にも最低件数を配る\n`common/sampling.py` の本物のコードです。"),
    (C, '''from common.sampling import stratified_sample
show(stratified_sample, 6, 25)'''),
    (M, "## 2. 抜き取りを再現し、本番と試験の分布を比べる\n同じ seed なら同じ 120 件になるか。ラベルの割合は本番とどれだけ違うか。"),
    (C, '''from collections import Counter
from common import kit
g = lab("run_golden", "lab02_golden_set")
pool, golden = kit.load_jsonl("inquiries_pool.jsonl"), kit.load_jsonl("golden_inquiries.jsonl")
again = stratified_sample(pool, key=g.stratum, n=120, min_per_stratum=3, seed=7)
print("seed=7 で抜き直すと:", "同じ 120 件" if [r["id"] for r in again] == [r["id"] for r in golden] else "違う")
cp, cg = Counter(r["label"] for r in pool), Counter(r["label"] for r in golden)
rows = [[x, cp[x], kit.pct(cp[x] / len(pool)), cg[x], kit.pct(cg[x] / len(golden))] for x in g.LABELS]
print(kit.table(rows, ["ラベル", "本番", "割合", "試験", "割合"]))
dp, dg = Counter(r["difficulty"] for r in pool), Counter(r["difficulty"] for r in golden)
for d in ("easy", "rule", "multi"):
    print(f"難しさ {d:<5} 本番 {kit.pct(dp[d] / len(pool))} → 試験 {kit.pct(dg[d] / len(golden))}")'''),
    (M, "## 3. 層の重み ― 本番での割合 ÷ 試験での割合\n全体の正答率を言うときは、この重みで本番の割合に戻します（P3 の「本番の割合に戻した正答率」）。"),
    (C, '''w = g.strata_weights(pool, golden)
cp2, cg2 = Counter(map(g.stratum, pool)), Counter(map(g.stratum, golden))
rows = [[k.replace("|", " / "), cp2[tuple(k.split("|"))], cg2[tuple(k.split("|"))], f"{v:.2f}"]
        for k, v in sorted(w.items(), key=lambda kv: kv[1])]
print(kit.table(rows, ["層（ラベル / 難しさ）", "本番", "試験", "重み"]))
print(f"層の数 {len(w)}、重みの範囲 {min(w.values()):.2f}〜{max(w.values()):.2f}")'''),
    (M, "## 4. 件数を 4 倍にすると、区間の幅は半分になる\n正答率 90% のときの Wilson の 95% 区間（`common/stats.py`）。"),
    (C, '''from common import stats
rows = []
for n in (30, 120, 480, 1920):
    lo, hi = stats.wilson(round(0.9 * n), n)
    rows.append([n, kit.ci_str(lo, hi), f"±{100 * (hi - lo) / 2:.1f}"])
print(kit.table(rows, ["件数", "95% 区間", "半幅（ポイント）"]))
print("±3 ポイントで知りたいなら（p=0.9）:", stats.n_for_margin(0.03, 0.9), "件 /（p=0.5）:", stats.n_for_margin(0.03, 0.5), "件")'''),
    (M, "## 5. お手本（few-shot）からの漏れ\nお手本 12 件と、用件がほぼ同じ（3 文字の Jaccard ≥ 0.8）試験の問い合わせを探します。"),
    (C, '''from common.sampling import leakage
shots = kit.load_jsonl("fewshot_inquiries.jsonl")
hits = leakage(golden, shots, threshold=0.8)
print(f"お手本 {len(shots)} 件と、ほぼ同じ用件の試験の問い合わせ: {len(set(h['test'] for h in hits))} 件")
for h in hits:
    print(f"   試験 {h['test']} ≈ お手本 {h['shot']}  (J={h['jaccard']})")'''),
    (M, "## 6. 似た文の塊 ― 実効の件数は 120 より少ない\n用件がほぼ同じものを 1 つの塊にまとめて数えます。"),
    (C, '''show(g.near_dup_clusters, 0, 16)
print()
print("試験 120 件 →", g.near_dup_clusters(golden), "塊")'''),
    (M, "## 7. データカードを書く\nラボの本物の実行（`run_golden.py`）が書いた `out/dataset_card.md` を開きます。"),
    (C, '''import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    g.main([])
print("# lab02_golden_set/out/dataset_card.md（長い行は折り返して表示）")
for line in open("lab02_golden_set/out/dataset_card.md", encoding="utf-8").read().splitlines():
    while len(line) > 50:
        print(line[:50]); line = "    " + line[50:]
    print(line)'''),
    (M, "## 8. 例題 ― 120 件・正答率 90% の幅を手で出す\nWilson の式を一つずつ計算し、`stats.wilson` の答えと比べます。"),
    (C, '''import math
n, k, z = 120, 108, 1.96               # 正答 108/120 = 90%
p = k / n
den = 1 + z * z / n                    # 1 + z²/n
center = (p + z * z / (2 * n)) / den   # 真ん中は 0.9 より少し 0.5 側へ寄る
half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
print(f"p={p:.3f}  分母={den:.4f}  真ん中={center:.4f}  半幅={half:.4f}")
print(f"手計算  [{100 * (center - half):.1f}, {100 * (center + half):.1f}]")
lo, hi = stats.wilson(k, n)
print(f"stats.wilson  [{100 * lo:.1f}, {100 * hi:.1f}]  半幅 ±{100 * (hi - lo) / 2:.1f} ポイント")
print(f"（正規近似なら ±{100 * z * math.sqrt(p * (1 - p) / n):.1f} ポイント）")'''),
])

# ---------------------------------------------------------------- P3
BOOKS["p03_classify_extract.ipynb"] = nb(
    "P3 分類と抽出の指標",
    "ソラハ電機の問い合わせ分類（6 ラベル）と、ツバクロ少額短期保険の請求書の項目抽出（6 項目）を、"
    "混同行列・適合率と再現率・マクロ F1・自信の較正・厳密な照合とそろえた照合で測ります。"
    "応答は講師が Opus 5.5 / Sonnet 5.5（effort high）で回した本物の記録です。", [
    (M, "## 1. 分類の依頼文と、手引きの規則\n依頼文は `prompts/classify.md`、手引きは `data/guide_inquiries.md`（長い行は折り返して表示）。"),
    (C, '''from common import kit, llm as L, metrics as M, stats
for path, a, b in (("lab03_classify_extract/prompts/classify.md", 0, 7), ("data/guide_inquiries.md", 8, 12)):
    print("#", path)
    for line in open(path, encoding="utf-8").read().splitlines()[a:b]:
        while len(line) > 46:
            print("  ", line[:46]); line = "    " + line[46:]
        print("  ", line)'''),
    (M, "## 2. 一件を分類させる\n到着から 60 日目の不具合の申し出。手引きの R2 では「修理・故障」です。"),
    (C, '''rc = lab("run_classify", "lab03_classify_extract")
golden = kit.load_jsonl("golden_inquiries.jsonl")
hard = kit.load_jsonl("golden_inquiries_v2_hard.jsonl")
P = "replay" if PROVIDER == "mock" else PROVIDER
r = next(x for x in golden if x["id"] == "INQ-0004")
print(rc._render(r))
a = kit.parser("demo").parse_args(["--provider", P, "--model", "claude-opus-5-5"])
with safe():
    x = rc.classify_one(r, a)
    print("→ 正解", x["label"], "/ 予測", x["pred"], "/ 決め手", x["rule"], "/ 自信", x["confidence"])'''),
    (M, "## 3. 120 件を分類し、混同行列を作る（Opus 5.5）\n行が正解、列が予測。対角線の外に数字があれば、それが取り違えです。"),
    (C, '''RUNS = {}
def run_set(model, which):
    a = kit.parser("demo").parse_args(["--provider", P, "--model", model])
    return [rc.classify_one(r, a) for r in (golden if which == "v1" else hard)]
with safe():
    for m in ("claude-opus-5-5", "claude-sonnet-5-5"):
        for s in ("v1", "v2"):
            RUNS[m, s] = run_set(m, s)
    rep = rc.report(RUNS["claude-opus-5-5", "v1"])
    rows = [[t] + [rep["confusion"][t][p] or "." for p in rc.LABELS] for t in rc.LABELS]
    print(kit.table(rows, ["正解＼予測"] + [c[:2] for c in rc.LABELS]))
    k, n = sum(x["correct"] for x in RUNS["claude-opus-5-5", "v1"]), len(golden)
    print(f"正答 {k}/{n}  Wilson の 95% 区間 {kit.ci_str(*stats.wilson(k, n))}")'''),
    (M, "## 4. 適合率・再現率・F1 と、マクロ・マイクロの平均\n`common/metrics.py` の本物のコードです。"),
    (C, '''show(M.classification_report)'''),
    (M, "## 5. 難問 48 件（v2）のラベル別の表 ― 全問正解なのにマクロ F1 は 0.667\n件数 0 のラベルは F1 が 0 になり、マクロ平均を引き下げます。"),
    (C, '''rep2 = rc.report(RUNS["claude-opus-5-5", "v2"])
rows = [[c, v["support"], f"{v['precision']:.2f}", f"{v['recall']:.2f}", f"{v['f1']:.2f}"]
        for c, v in rep2["per_class"].items()]
print(kit.table(rows, ["ラベル", "件数", "適合率", "再現率", "F1"]))
print(f"正答率 {kit.pct(rep2['accuracy'])} / マイクロ F1 {rep2['micro_f1']:.3f} / マクロ F1 {rep2['macro_f1']:.3f}")
present = [v["f1"] for v in rep2["per_class"].values() if v["support"]]
print(f"件数のあるラベル {len(present)} 個だけで平均すると {sum(present) / len(present):.3f}")'''),
    (M, "## 6. 自信の較正（ECE）のコード\n自信を 5 つの区間に分け、区間ごとの「平均の自信」と「実際の正答率」の差を、件数の重みで足します。"),
    (C, '''show(M.ece)'''),
    (M, "## 7. 自信と正答のずれを測る ― 全問正解なのに自信は低め\n実際の正答率は 1.00。自信の方が低いので、ずれは「自信が低すぎる」側です。"),
    (C, '''for (m, s) in (("claude-opus-5-5", "v1"), ("claude-sonnet-5-5", "v1"), ("claude-opus-5-5", "v2")):
    rp = rc.report(RUNS[m, s])
    bins = [f"[{b['bin']}] {b['n']}件 自信{b['conf']:.2f} 正答{b['acc']:.2f}" for b in rp["reliability"] if b["n"]]
    print(f"{m.replace('claude-', ''):<11} {s}  ECE = {rp['ece']:.3f}")
    for b in bins:
        print("     ", b)'''),
    (M, "## 8. 抽出 ― 一枚の請求書と、取り出した 6 項目\n和暦（R8.9.8）・全角の数字・日額と請求額が並ぶ、紛らわしい一枚です。"),
    (C, '''rx = lab("run_extract", "lab03_classify_extract")
claims = kit.load_jsonl("claims.jsonl")
d = next(x for x in claims if x["id"] == "CLM-006")
for line in d["text"].splitlines():
    while len(line) > 46:
        print(line[:46]); line = "  " + line[46:]
    print(line)
a = kit.parser("demo").parse_args(["--provider", P, "--model", "claude-opus-5-5"])
with safe():
    e = rx.extract_one(d, a)
    rows = [[f, repr(d["gold"][f]), repr(e["pred"].get(f))] for f in rx.FIELDS]
    print(kit.table(rows, ["項目", "正解", "Opus の出力"]))'''),
    (M, "## 9. そろえてから比べる ― normalized の照合のコード\n全角→半角、「30,000 円」→ 30000、「2026/9/8」→「2026-09-08」。"),
    (C, '''show(rx.norm, 12, 19)
print()
for f, v in (("claim_amount", "３０,０００円"), ("claim_amount", 30000), ("incident_date", "2026/9/8"),
             ("claimant", "篠宮 彩花 "), ("receipt_attached", "あり")):
    print(f"norm({f!r}, {v!r}) → {rx.norm(f, v)!r}")'''),
    (M, "## 10. 48 枚を 2 つのモデルで ― strict と normalized\n比べ方で点が変わるなら、採点の仕方を疑います。"),
    (C, '''EX = {}
with safe():
    for m in ("claude-sonnet-5-5", "claude-opus-5-5"):
        a = kit.parser("demo").parse_args(["--provider", P, "--model", m])
        EX[m] = [rx.extract_one(d, a) for d in claims]
    sc = {(m, k): M.field_scores([r["gold"] for r in EX[m]], [r["pred"] for r in EX[m]], rx.FIELDS,
                                 norm=rx.norm if k == "norm" else None) for m in EX for k in ("strict", "norm")}
    rows = [[f] + [kit.pct(sc[m, k]["per_field"][f]) for m in EX for k in ("strict", "norm")] for f in rx.FIELDS]
    print(kit.table(rows, ["項目", "Sonnet 厳密", "そろえて", "Opus 厳密", "そろえて"]))
    for m in EX:
        print(f"{m}: 全項目が合った請求書 {kit.pct(sc[m, 'strict']['doc_all_correct'])}（n={len(EX[m])}）")'''),
    (M, "## 11. 飽和 ― 満点の試験は何も言わない\n3 つの試験で 2 つのモデルを並べます。差が残るのは費用だけです。"),
    (C, '''rows = []
for name, get in (("分類 v1 120件", lambda m: RUNS[m, "v1"]), ("分類 v2 難問48件", lambda m: RUNS[m, "v2"]),
                  ("抽出 48件", lambda m: EX[m])):
    for m in ("claude-sonnet-5-5", "claude-opus-5-5"):
        rr = get(m)
        k = sum(x["correct"] for x in rr) if "correct" in rr[0] else sum(x["pred"] == x["gold"] for x in rr)
        lo, _ = stats.wilson(k, len(rr))
        rows.append([name, m.replace("claude-", ""), f"{k}/{len(rr)}", f"{100 * lo:.1f}%", f"{sum(x['cost_usd'] for x in rr):.4f}"])
print(kit.table(rows, ["試験", "モデル", "正答", "区間の下限", "費用 USD"]))'''),
    (M, "## 12. 例題 ― 小さな混同行列から F1 を手で出す\n10 件の小さな例。返品・交換 5 件、修理・故障 5 件。"),
    (C, '''truth = ["返品・交換"] * 5 + ["修理・故障"] * 5
pred = ["返品・交換"] * 4 + ["修理・故障"] + ["返品・交換"] * 2 + ["修理・故障"] * 3
for c in ("返品・交換", "修理・故障"):
    tp = sum(t == c and p == c for t, p in zip(truth, pred))
    fp = sum(t != c and p == c for t, p in zip(truth, pred))
    fn = sum(t == c and p != c for t, p in zip(truth, pred))
    pr, re_ = tp / (tp + fp), tp / (tp + fn)
    print(f"{c}: TP={tp} FP={fp} FN={fn}  適合率 {tp}/{tp + fp}={pr:.3f}  再現率 {tp}/{tp + fn}={re_:.3f}"
          f"  F1={2 * pr * re_ / (pr + re_):.3f}")
rep = M.classification_report(truth, pred, ["返品・交換", "修理・故障"])
print("metrics の答え:", {c: round(v["f1"], 3) for c, v in rep["per_class"].items()},
      f"マクロ F1 {rep['macro_f1']:.3f} / 正答率 {rep['accuracy']:.1f}")'''),
])

# ---------------------------------------------------------------- P4
BOOKS["p04_rag_eval.ipynb"] = nb(
    "P4 RAG の評価 ― 検索と回答を分けて測る",
    "ヒイラギ運輸（架空）の社内規程 14 本と質問 30 問で、検索（BM25）と回答（Opus 5.5 / Sonnet 5.5）を分けて測ります。"
    "要素の照合・断る率・忠実さの判定（判定役は回答者と別のモデル）と、照合そのものの誤りを読みます。", [
    (M, "## 1. 検索の指標のコード ― 再現率・逆順位・割引累積利得\n`common/metrics.py` の本物のコードです。"),
    (C, '''from common import kit, llm as L, metrics as M, stats
show(M.recall_at_k)
show(M.mrr)
show(M.ndcg_at_k)'''),
    (M, "## 2. 一つの問いで検索を測り、30 問の平均を出す\n根拠の規程が 2 本ある問い Q22 の、BM25 の上位 5 件。"),
    (C, '''rr = lab("run_rag", "lab04_rag_eval")
pol = kit.load_json("policies.json")
docs, qs = pol["docs"], {q["id"]: q for q in pol["questions"]}
bm = rr.BM25(docs)
q = qs["Q22"]
ranked = [i for i, _ in bm.search(q["question"], 5)]
print(q["question"]); print("上位 5 件:", ranked, "/ 正解の根拠:", q["gold_docs"])
gold = set(q["gold_docs"])
print(f"recall@1 {M.recall_at_k(ranked, gold, 1):.2f} / recall@3 {M.recall_at_k(ranked, gold, 3):.2f}"
      f" / 逆順位 {M.mrr(ranked, gold):.2f} / nDCG@3 {M.ndcg_at_k(ranked, gold, 3):.3f}")
rk = [x for x in pol["questions"] if x["gold_docs"]]
avg = lambda f: sum(f([i for i, _ in bm.search(x["question"], 14)], set(x["gold_docs"])) for x in rk) / len(rk)
print(f"根拠のある {len(rk)} 問の平均: recall@3 {avg(lambda r, g: M.recall_at_k(r, g, 3)):.3f} / 逆順位 {avg(M.mrr):.3f}"
      f" / nDCG@3 {avg(lambda r, g: M.ndcg_at_k(r, g, 3)):.3f}")'''),
    (M, "## 3. 要素の照合と、断ったかどうかの判定（照合 v1）\n答えに入るべき語が全部あるか。「規程に記載がありません」で始まれば断ったとみなす…はずでした。"),
    (C, '''show(rr.check_answer)
print("断りの文:", pol["abstain"])
print("Q11 で入るべき語:", qs["Q11"]["must"])'''),
    (M, "## 4. 30 問を回答させ、照合 v1 で採点する（回答 Opus 5.5）\nラボの本物の実行（`run_rag.py`）の出力。長い回答の行は省きます。"),
    (C, '''import io, contextlib
P = "replay" if PROVIDER == "mock" else PROVIDER
def quiet(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rr.main(["--provider", P, "--all"] + argv)
    return buf.getvalue().splitlines()
with safe():
    for line in quiet(["--model", "claude-opus-5-5"]):
        if line.strip() and not line.startswith(("   ×", "   20", "検索", "   上位")):
            print(line[:96])'''),
    (M, "## 5. 根拠を抜いたら、断れるか（断る率）\n検索結果から正解の根拠の規程を抜いた 26 問。根拠が無いのに数字を作ったら失格です。"),
    (C, '''with safe():
    for m in ("claude-opus-5-5", "claude-sonnet-5-5"):
        out = quiet(["--model", m, "--condition", "degraded"])
        runs = kit.read_jsonl(f"lab04_rag_eval/out/runs_rag_degraded_{kit.slug(m)}.jsonl")
        ans = [r for r in runs if not r["abstained"]]
        print(f"{m:<18} 根拠を抜いた {len(runs)} 問 → 断った {len(runs) - len(ans)} 問 / 断らずに答えた {len(ans)} 問")
        print("   例", runs[0]["id"], "の回答:", repr(runs[0]["answer"][:40]))'''),
    (M, "## 6. 忠実さの判定 ― 判定役は回答者と別のモデル\n回答を主張に分け、渡した規程から導けるかを判定します（依頼文 `prompts/faithfulness.md`）。"),
    (C, '''print("# lab04_rag_eval/prompts/faithfulness.md（長い行は折り返して表示）")
for n, line in enumerate(open("lab04_rag_eval/prompts/faithfulness.md", encoding="utf-8").read().splitlines(), 1):
    cut = 44 if sum(ord(ch) > 0x2E80 for ch in line) > 20 else 200
    print(f"{n:4d}  {line[:cut]}")
    if len(line) > cut:
        print("      " + line[cut:])'''),
    (M, "## 7. 忠実さを測る（回答 Opus 5.5・判定役 Sonnet 5.5）\n断らなかった回答だけを判定します。"),
    (C, '''with safe():
    out = quiet(["--model", "claude-opus-5-5", "--judge"])
    runs = kit.read_jsonl("lab04_rag_eval/out/runs_rag_normal_opus-5-5.jsonl")
    f = [r for r in runs if r.get("faithfulness") is not None]
    print(f"判定した回答 {len(f)} 問 / 忠実さの平均 {sum(r['faithfulness'] for r in f) / len(f):.3f}")
    print(f"主張の数 {sum(len(r['claims']) for r in f)} / 導けないとされた主張 "
          f"{sum(1 for r in f for c in r['claims'] if not c.get('supported'))}")
    for r in f:
        if r["faithfulness"] < 1:
            print(f"   {r['id']}: 忠実さ {r['faithfulness']:.2f}（主張 {len(r['claims'])} 個）")
    print([line for line in out if line.startswith("費用")][0])'''),
    (M, "## 8. 照合の誤りを読む ― × を全件読む\n照合 v1 で × になった問いを、v2（断りの判定と別表記を直したもの）と並べます。"),
    (C, '''import inspect
src, first = inspect.getsourcelines(rr.check_answer_v2)
print("# lab04_rag_eval/run_rag.py", first, "行目から（長い行は折り返して表示）")
for n, line in enumerate(src, first):
    line = line.rstrip()
    print(f"{n:4d}  {line[:88]}")
    if len(line) > 88:
        print("      " + " " * 8 + line[88:])
print("別表記:", rr.EXTRA_ALIASES)'''),
    (M, "## 9. 照合 v1 と v2 を並べる ― 外れの多くは照合の誤り\n2 つの回答役の、v1 で × になった問い。"),
    (C, '''for m in ("claude-opus-5-5", "claude-sonnet-5-5"):
    runs = kit.read_jsonl(f"lab04_rag_eval/out/runs_rag_normal_{kit.slug(m)}.jsonl")
    print(f"{m}: v1 {sum(r['correct'] for r in runs)}/30 → v2 {sum(r['correct_v2'] for r in runs)}/30")
    for r in runs:
        if not r["correct"]:
            head = " ".join(r["answer"].replace("*", "").replace("#", "").split())[:26]
            print(f"   {r['id']} v1 × → v2 {'○' if r['correct_v2'] else '×'}  回答の頭:「{head}」")'''),
    (M, "## 10. 忠実さの判定も間違える ― Q13\n「導けない」とされた主張と、根拠の規程を並べます。"),
    (C, '''r13 = next(r for r in kit.read_jsonl("lab04_rag_eval/out/runs_rag_normal_opus-5-5.jsonl") if r["id"] == "Q13")
print("問い:", qs["Q13"]["question"])
for c in r13["claims"]:
    if not c.get("supported"):
        print("導けないとされた主張:", c["claim"])
d10 = next(d for d in docs if d["id"] == "D10")
print(f"根拠の規程 [{d10['id']}] {d10['title']}:")
t = d10["text"]
while t:
    print("   ", t[:44]); t = t[44:]'''),
    (M, "## 11. 例題 ― 三問で上位三件の再現率と逆順位を手で出す\nBM25 の上位 3 件と正解の根拠を見比べ、手で数えてから metrics の答えと比べます。"),
    (C, '''for qid in ("Q01", "Q10", "Q22"):
    q = qs[qid]
    top = [i for i, _ in bm.search(q["question"], 14)]
    gold = set(q["gold_docs"])
    hit = [i for i in top[:3] if i in gold]
    first = next(n for n, i in enumerate(top, 1) if i in gold)
    print(f"{qid} 上位3 {top[:3]} 正解 {sorted(gold)} → 再現率 {len(hit)}/{len(gold)}"
          f" / 最初の正解は {first} 位 → 逆順位 1/{first}={1 / first:.3f}")
    print(f"     metrics: recall@3 {M.recall_at_k(top, gold, 3):.3f} / MRR {M.mrr(top, gold):.3f}")'''),
])
