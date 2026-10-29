"""P8〜P12 のノートブック。部品は _nbkit.py、全体は build_notebooks.py。"""
from _nbkit import C, M, nb

BOOKS = {}

# 表示幅（全角 2）で切る小さな道具。録画の 1 画面に収めるため、長い行の後ろを「…」にする
CUT = '''def cut(s, w=100):                  # 表示幅（全角 2）で切って、後ろを「…」にする
    s, n = s.replace("\\n", " "), 0
    for i, ch in enumerate(s):
        n += 2 if ord(ch) > 0x2E80 else 1
        if n > w:
            return s[:i] + "…"
    return s'''

# 表示幅（全角 2）で折り返す
WRAP = '''def wrap(s, w=92):
    for line in s.splitlines():
        out, n = "", 0
        for ch in line:
            k = 2 if ord(ch) > 0x2E80 else 1
            if n + k > w:
                print(out); out, n = "", 0
            out, n = out + ch, n + k
        print(out)'''

# ---------------------------------------------------------------- P8
BOOKS["p08_stats.ipynb"] = nb(
    "P8 差は本物か",
    "区間・0 件の上限・対の比較（McNemar・ブートストラップ・並べ替え）・塊の標準誤差・必要な件数・多重比較を、"
    "講師の本物の実行の結果（lab03 と lab09 の out/）で計算します。LLM は呼びません。", [
    (M, "## 1. 同じ試験をもう一度やったら（模擬）\n本当の正答率が 90% のモデルでも、問いを引き直すたびに点は動きます。"),
    (C, '''import random
from common import kit, stats
rng = random.Random(1)
accs = []
for t in range(10):
    k = sum(rng.random() < 0.9 for _ in range(120))
    lo, hi = stats.wilson(k, 120)
    accs.append(k / 120)
    print(f"{t + 1:2d} 回目: {k}/120 = {kit.pct(k / 120)}  95%区間 {kit.ci_str(lo, hi)}"
          f"  90% を {'含む' if lo <= 0.9 <= hi else '外す'}")
print(f"最小 {kit.pct(min(accs))} 〜 最大 {kit.pct(max(accs))}（同じモデル・同じ腕前でも、これだけ動く）")'''),
    (M, "## 2. Wilson の区間\n`common/stats.py` の本物のコードと、正規近似との違い。"),
    (C, '''show(stats.wilson)
rows = []
for k, n, what in [(120, 120, "分類 v1（両モデル）"), (48, 48, "分類 v2 難問"), (108, 120, "仮に 108/120"),
                   (0, 12, "漏えい（lab11）")]:
    lo, hi = stats.wilson(k, n)
    p = k / n
    se = (p * (1 - p) / n) ** 0.5
    rows.append([what, f"{k}/{n}", kit.ci_str(lo, hi), kit.ci_str(max(0, p - 1.96 * se), min(1, p + 1.96 * se))])
print()
print(kit.table(rows, ["実験", "結果", "Wilson 95%", "正規近似 95%"]))'''),
    (M, "## 3. 0 件でも安全とは言えない ― 3 の法則\n0/n のときの上限（95%）は、だいたい 3/n。"),
    (C, '''rows = []
for n in (12, 30, 120, 300, 1500):
    lo, hi = stats.wilson(0, n)
    rows.append([n, f"0/{n}", kit.pct(hi), kit.pct(stats.rule_of_three(n))])
print(kit.table(rows, ["件数", "結果", "Wilson の上限", "3 の法則 3/n"]))
print("上限を 0.2% まで下げたいなら 3 / 0.002 =", round(3 / 0.002), "件（それで 0 件なら）")'''),
    (M, "## 4. 対の比較 ― 食い違った問いだけを見る\n基準（全文の手引き）と候補（短くした依頼文）を、同じ v2 難問 48 問で比べます（Sonnet・本物の実行の記録）。"),
    (C, '''base = {r["id"]: r for r in kit.read_jsonl("lab03_classify_extract/out/runs_classify_v2_sonnet-5-5.jsonl")}
cand = {r["id"]: r for r in kit.read_jsonl("lab09_ci_gate/out/runs_candidate_v2_sonnet-5-5.jsonl")}
ids = sorted(base)
a, b = [base[i]["correct"] for i in ids], [cand[i]["correct"] for i in ids]
both = sum(x and y for x, y in zip(a, b))
none = sum((not x) and (not y) for x, y in zip(a, b))
only_a, only_b = stats.discordant(a, b)
print(kit.table([["基準 ○", both, only_a], ["基準 ×", only_b, none]], ["", "候補 ○", "候補 ×"]))
print(f"\\n両方正解 {both} 問・両方不正解 {none} 問は、差について何も言わない")
print(f"見るのは食い違った {only_a + only_b} 問だけ: 基準だけ正解 {only_a} / 候補だけ正解 {only_b}")'''),
    (M, "## 5. 対のブートストラップと並べ替え検定\n同じ問いの差（候補 − 基準）を引き直して、差の区間と p 値を出します。"),
    (C, '''show(stats.paired_bootstrap)
pb = stats.paired_bootstrap(a, b, seed=0)
p_mc = stats.mcnemar_exact(only_a, only_b)
p_perm = stats.paired_permutation(a, b, B=5000, seed=0)
print(f"\\n正答 {sum(a)} → {sum(b)}  差 {pb['diff']:+.3f}  対のブートストラップ 95%区間 [{pb['lo']:+.3f}, {pb['hi']:+.3f}]")
print(f"McNemar p={p_mc:.2g} / 並べ替え p={p_perm:.2g}")
la, ha = stats.wilson(sum(a), len(a))
lb, hb = stats.wilson(sum(b), len(b))
print(f"対にしないで区間だけ並べると: 基準 {kit.ci_str(la, ha)} / 候補 {kit.ci_str(lb, hb)}")'''),
    (M, "## 6. 塊の標準誤差\n同じ種類の難問（8 問ずつ 6 種類）は一緒に崩れます。素朴な SE は小さすぎます（Miller 2024）。"),
    (C, '''show(stats.cluster_se)
scen = [base[i]["scenario"] for i in ids]
naive, clus = stats.naive_se(b), stats.cluster_se(b, scen)
print(f"\\n候補の正答（{len(set(scen))} 種類の塊）: 素朴な SE {naive:.3f} / 塊の SE {clus:.3f}（{clus / naive:.2f} 倍）")
ss = sorted(set(scen))
for part in (ss[:3], ss[3:]):
    print("   " + " / ".join(f"{s} {sum(b[j] for j in range(len(b)) if scen[j] == s)}/8" for s in part))'''),
    (M, "## 7. 検出力 ― 小さな差を見つけるには何問要るか（模擬）\n本当の差が 3 ポイントあるとき、試験を 200 回やって「差あり」と言えた回数を数えます。"),
    (C, '''rng = random.Random(0)
pd, delta = 0.29, 0.03            # 食い違う問いの割合と、本当の差 3 ポイント

def found(n):                     # 1 回の比較で「差あり」と言えたか（正規近似の McNemar）
    d = sum(rng.random() < pd for _ in range(n))
    c = sum(rng.random() < (pd + delta) / (2 * pd) for _ in range(d))   # 候補だけ正解
    return d > 0 and abs(c - (d - c)) / d ** 0.5 > 1.96

for n in (48, 500, 2500):
    hits = sum(found(n) for _ in range(200))
    print(f"{n:5d} 問の試験を 200 回: 差 3 ポイントを見つけた {hits:3d} 回（{hits / 2:.0f}%）")'''),
    (M, "## 8. 必要な件数を計算する\n対あり・α=0.05 両側・検出力 80%。食い違う割合は 48 問の実測（14/48）を使います。"),
    (C, '''show(stats.n_paired, 2, 6)
print(" 123      return ceil((za·√p_disc + zb·√(p_disc − delta²))² / delta²)   ← 長い行を縮めて表示")
pd = (only_a + only_b) / len(ids)
rows = [[f"{int(d * 100)} ポイント", stats.n_paired(d, max(pd, d * 1.5))] for d in (0.03, 0.05, 0.10, 0.20)]
print(f"\\n食い違う問いの割合 {pd:.2f} と仮定")
print(kit.table(rows, ["見つけたい差", "必要な問いの数"]))'''),
    (M, "## 9. 多重比較の補正（Holm）\n難問の種類ごとに 6 回検定すると、どれかが偶然「有意」になりやすい。"),
    (C, '''show(stats.holm)
pv = {}
for s in ss:
    j = [i for i in range(len(b)) if scen[i] == s]
    pv[s] = stats.mcnemar_exact(*stats.discordant([a[i] for i in j], [b[i] for i in j]))
keep = stats.holm(pv)
for s, p in sorted(pv.items(), key=lambda kv: kv[1]):
    print(f"   {s:14s} p={p:.3f}  補正前 {'有意' if p < 0.05 else '-'} / Holm {'有意' if keep[s] else '-'}")'''),
    (M, "## 10. 方法で結論が割れるとき\n短くした依頼文の下で、Sonnet と Opus を同じ 48 問で比べます（lab09 の本物の実行の記録）。"),
    (C, '''opus = {r["id"]: r["correct"] for r in kit.read_jsonl("lab09_ci_gate/out/runs_candidate_v2_opus-5-5.jsonl")}
x, y = b, [opus[i] for i in ids]
s_only, o_only = stats.discordant(x, y)
bs = stats.paired_bootstrap(x, y, seed=0)
print(f"短い依頼文で Sonnet {sum(x)}/48・Opus {sum(y)}/48（同じ 48 問）")
print(f"Sonnet だけ正解 {s_only} / Opus だけ正解 {o_only}")
print(f"McNemar（正確）p={stats.mcnemar_exact(s_only, o_only):.3f}  → 5% では差があるとは言えない")
print(f"対のブートストラップ 95%区間 [{bs['lo']:+.3f}, {bs['hi']:+.3f}]  → 0 を含まない")
print("件数が少ないと、方法で結論が割れる。方法は先に 1 つ決め、割れたら件数を増やす")'''),
    (M, "## 11. 例題 ― 食い違い 14 対 0 を手で検定する\n食い違いが本当に五分五分なら、14 問とも同じ側に寄る確率はどれだけか。"),
    (C, '''n = 14 + 0                         # 基準だけ正解 14 問 / 候補だけ正解 0 問
one_side = 0.5 ** n                # 14 問とも基準の側に寄る確率
print(f"食い違い {n} 問が全部片側に寄る確率 = 0.5^{n} = {one_side:.6f}")
print(f"両側の p 値 = 2 × {one_side:.6f} = {2 * one_side:.6f}")
print(f"stats.mcnemar_exact(14, 0)     = {stats.mcnemar_exact(14, 0):.6f}")
print("→ p≈0.0001。偶然で 14 対 0 になることは、まず無い")'''),
    (M, "## 12. 例題 ― 3 ポイントの差に要る問いの数\n`stats.n_paired` の式（Connor 1987 の近似）を一つずつ計算します。"),
    (C, '''import math
d, pd = 0.03, 14 / 48              # 見つけたい差 3 ポイント、食い違う割合（実測）
za, zb = 1.96, 0.8416              # 両側 5% と、検出力 80%
r1, r2 = math.sqrt(pd), math.sqrt(pd - d * d)
num = (za * r1 + zb * r2) ** 2
print(f"√pd = {r1:.4f}、√(pd − d²) = {r2:.4f}")
print(f"分子 = ({za} × {r1:.4f} + {zb} × {r2:.4f})² = {num:.4f}")
print(f"必要な問い = 分子 ÷ d² = {num:.4f} ÷ {d * d:.4f} = {num / (d * d):.0f}")
print(f"stats.n_paired(0.03, {pd:.4f}) = {stats.n_paired(d, pd)}")
print("→ 約 2,500 問。いまの 48 問では、3 ポイントの差は見えない")'''),
])

# ---------------------------------------------------------------- P9
BOOKS["p09_ci_gate.ipynb"] = nb(
    "P9 回帰の関門（CI ゲート）",
    "費用を下げるために分類の依頼文を短くした「候補」を、いまの本番（基準）と同じ問いで比べ、出してよいかを"
    "非劣性・層の床・無効な出力の 3 つの決まりで決めます。", [
    (M, "## 1. 基準と候補を決める\n関門の決まり（gate_config.json）と、短くした依頼文。"),
    (C, '''from common import kit, stats
show_file("lab09_ci_gate/gate_config.json")
full = open("lab03_classify_extract/prompts/classify.md", encoding="utf-8").read()
full = full.format(guide=kit.load_text("guide_inquiries.md"))
short = open("lab09_ci_gate/prompts/classify_trimmed.md", encoding="utf-8").read()
print(f"\\n基準の依頼文（分類の手引きつき）{len(full)} 字 / 候補の依頼文（短くした）{len(short)} 字")
show_file("lab09_ci_gate/prompts/classify_trimmed.md", 2, 4)'''),
    (M, "## 2. 候補を v2 難問 48 問で回す\n講師の本物の実行（Sonnet と Opus）の記録を再生します。"),
    (C, '''import io, contextlib
P = "replay" if PROVIDER == "mock" else PROVIDER
rc = lab("run_candidate", "lab09_ci_gate")
with safe():
    for m in ("claude-sonnet-5-5", "claude-opus-5-5"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc.main(["--provider", P, "--all", "--model", m])
        print(f"{m:<18}", [l for l in buf.getvalue().splitlines() if "候補の正答" in l][0])
print("基準（全文の手引き）は両モデルとも 48/48（lab03）")'''),
    (M, "## 3. 非劣性 ―「勝った」ではなく「負けていない」を言う\n差の下限（片側 95%）が −0.03 より上なら「負けていない」。"),
    (C, '''gate = lab("gate", "lab09_ci_gate")
cfg = kit.read_json("lab09_ci_gate/gate_config.json")
pairs, _ = gate.default_pairs()
for name, bp, cp in pairs:
    r = gate.evaluate(gate.load(bp), gate.load(cp), cfg)
    ok = r["lower"] > -cfg["margin"]
    print(f"■ {name}")
    print(f"   差 {r['diff']:+.3f} / 下限 {r['lower']:+.3f} / 線 −{cfg['margin']:.2f}"
          f" → {'負けていない（通す）' if ok else '負けていないとは言えない（止める）'}")'''),
    (M, "## 4. 層の床 ― どの種類も大きくは落とさない\n全体の差だけでなく、種類（scenario）ごとに 25 ポイント超の落ち込みを止めます。"),
    (C, '''show(gate.evaluate, 15, 25)
r = gate.evaluate(gate.load(pairs[0][1]), gate.load(pairs[0][2]), cfg)
print(f"\\n{pairs[0][0]}:")
for s, k, ab, cb in r["slices"]:
    print(f"   {s:14s} n={k}  基準 {ab:.0%} → 候補 {cb:.0%}  {'✗ 床を割った' if ab - cb > cfg['floor'] else ''}")'''),
    (M, "## 5. gate.py を回す ― 終了コードで CI を止める\n3 つの組をまとめて判定します（長い行は後ろを省いて表示）。"),
    (C, CUT + '''
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    code = gate.main([])
for line in buf.getvalue().splitlines()[2:]:
    if line.strip():
        print(cut(line, 104))
print("gate.py の終了コード:", code, "（1 = 止める。CI ならここで止まる）")'''),
    (M, "## 6. CI に入れる形\n記録の再生だけで関門を回す例（このキットでは有効にしていない）。"),
    (C, '''print("依頼文・モデルを変えた PR で、記録の再生だけで関門を回す（新しい依頼は API を呼ばずに止まる）")
show_file("lab09_ci_gate/ci_example.yml", 3)'''),
    (M, "## 7. 評価の道具の失敗 ― 予算切れを「無効」と数えない\n予算の上限・記録なしで止まった呼び出しは、モデルの無効な出力ではない。"),
    (C, '''from common import llm as L
show_file("lab09_ci_gate/run_candidate.py", 59, 64)
print()
show(L._anthropic, 0, 2)'''),
    (M, "## 8. 例題 ― 満点同士でも差の下限は −2.2 ポイント\n食い違い 0 件のときは、Wilson の上限（片側 95% = 両側 90%）で幅を付けます。"),
    (C, '''n = 120
z = stats.z(0.90)
up = z * z / (n + z * z)           # 0/n のときの Wilson の上限は z²/(n+z²) にまとまる
print(f"z = {z:.4f}、上限 = {z * z:.4f} / ({n} + {z * z:.4f}) = {up:.4f}")
print(f"stats.wilson(0, 120, conf=0.90) の上限 = {stats.wilson(0, n, conf=0.90)[1]:.4f}")
r = gate.evaluate(gate.load(pairs[2][1]), gate.load(pairs[2][2]), cfg)
print(f"関門の計算（Opus → Sonnet）: 下限 {r['lower']:+.3f} > −0.03 → 通す、費用 {r['cost_base']:.2f} → {r['cost_cand']:.2f} USD")
for n in (40, 80, 100, 300):
    lo = -stats.wilson(0, n, conf=0.90)[1]
    print(f"   {n:3d} 問・満点同士なら: 下限 {100 * lo:+.1f} ポイント → {'通す' if lo > -0.03 else '止める'}")'''),
    (M, "## 9. 例題 ― 依頼文を短くした候補を止める\n関門の判定を、数字を追って確かめます（Sonnet・v2 難問 48 問）。"),
    (C, '''r = gate.evaluate(gate.load(pairs[0][1]), gate.load(pairs[0][2]), cfg)
nb_, nc_ = round(r["base_acc"] * r["n"]), round(r["cand_acc"] * r["n"])
print(f"基準 {nb_}/{r['n']} → 候補 {nc_}/{r['n']}、差 = ({nc_} − {nb_}) / {r['n']} = {r['diff']:+.3f}")
print(f"片側 95% の下限 {r['lower']:+.3f} < −0.03 → 非劣性を満たさない")
for s, k, ab, cb in r["slices"]:
    if ab - cb > cfg["floor"]:
        print(f"層の床: {s} {ab:.0%} → {cb:.0%}（{100 * (ab - cb):.0f} ポイント落ちた）")
cut_ = 1 - r["cost_cand"] / r["cost_base"]
print(f"費用 {r['cost_base']:.4f} → {r['cost_cand']:.4f} USD（{100 * cut_:.0f}% 安い）。安くなった分より、壊れた分が大きい")
print("判定:", "通す" if r["pass"] else "止める")'''),
])

# ---------------------------------------------------------------- P10
BOOKS["p10_online_eval.ipynb"] = nb(
    "P10 本番での評価",
    "シャドー運転・カナリア（割り当ての偏り SRM）・分布のずれ・人が見る抜き取りは **模擬**（乱数固定の作りもの・手順の説明用）。"
    "費用と待ち時間だけは、講師の本物の実行の記録から計算します。", [
    (M, "## 1. シャドー運転（模擬）\nAI の分類をお客様に出さずに記録し、人の分類と週ごとに比べます。"),
    (C, '''from collections import Counter
from common import kit, stats
on = lab("run_online", "lab10_online_eval")
rows = on.simulate()                       # 🔴 模擬: 乱数固定の作りもの
tbl = []
for w in range(1, 5):
    sub = [r for r in rows if r["week"] == w]
    crit = sum((r["human"], r["ai"]) in on.CRITICAL for r in sub)
    agree = sum(r["ai"] == r["human"] for r in sub) / len(sub)
    tbl.append([f"W{w}", len(sub), kit.pct(agree), crit, f"{100 * stats.wilson(crit, len(sub))[1]:.2f}%"])
print("シャドー運転（模擬・1〜4 週）")
print(kit.table(tbl, ["週", "件数", "人との一致", "重大な食い違い", "重大の率の上限"]))
print("決まり「重大の率の上限 < 0.2%」→ 一致率が 9 割を超えていても、満たさない")'''),
    (M, "## 2. 割り当ての偏り（SRM）を先に確かめる（模擬）\n流量の 10% に新しい依頼文を出したはずが、本当に 10% になっているか。"),
    (C, '''import io, contextlib
can = [r for r in rows if r["week"] in (5, 6)]
nc = sum(r["arm"] == "canary" for r in can)
nt = len(can) - nc
ec, et = len(can) * 0.1, len(can) * 0.9
chi = (nc - ec) ** 2 / ec + (nt - et) ** 2 / et
p = stats.chi2_sf(chi, 1)
print(f"割り当て: カナリア {nc} / 対照 {nt}（期待 {ec:.0f} / {et:.0f}）")
print(f"χ² = {chi:.3f}、p = {p:.3f} → {'比は正常。結果を読みに進む' if p > 0.001 else '比がおかしい。結果を読まない'}")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    on.main([])
line = [l for l in buf.getvalue().splitlines() if "再問い合わせ率" in l][0].strip()
print(line.split("、95%区間")[0])
print("   95%区間" + line.split("、95%区間")[1])'''),
    (M, "## 3. 分布のずれ ― χ² と PSI（模擬）\n6 週目に新製品が出て「使い方」の問い合わせが増えたら、試験セットは本番を代表しなくなる。"),
    (C, '''c1 = Counter(r["truth"] for r in rows if r["week"] <= 4)
c6 = Counter(r["truth"] for r in rows if r["week"] == 6)
stat, dof, p = stats.chi2_homogeneity(c1, c6)
tbl = [[x, kit.pct(c1[x] / sum(c1.values())), kit.pct(c6[x] / sum(c6.values()))] for x in on.LABELS]
print(kit.table(tbl, ["種類", "1〜4 週", "6 週"]))
print(f"\\nχ² = {stat:.1f}（自由度 {dof}）p = {p:.2g} / PSI = {stats.psi(c1, c6):.3f}")

def acc(ws):
    sub = [r for r in rows if r["week"] in ws]
    return sum(r["ai"] == r["truth"] for r in sub) / len(sub)
print(f"AI の正答（模擬なので正解は分かる）: 1〜4 週 {kit.pct(acc(range(1, 5)))} → 6 週 {kit.pct(acc([6]))}")'''),
    (M, "## 4. 人が見る抜き取りの二本立て（模擬）\n同じ 40 件/週でも、無作為と「自信の低い順」で見つかる誤りの数が違う。"),
    (C, '''import random
wk = [r for r in rows if r["week"] == 7]
errs = sum(r["ai"] != r["truth"] for r in wk)
rnd = random.Random(3).sample(wk, 40)
risk = sorted(wk, key=lambda r: (r["conf"], r["ai"] not in ("返品・交換", "修理・故障", "請求・支払い")))[:40]
f_r = sum(r["ai"] != r["truth"] for r in rnd)
f_k = sum(r["ai"] != r["truth"] for r in risk)
print(f"7 週目の AI の誤り {errs}/{len(wk)} 件")
print(f"   無作為 40 件で見つかる誤り {f_r} 件 → 全体の誤り率の推定に使える（{kit.pct(f_r / 40)}）")
print(f"   自信の低い順 40 件で見つかる誤り {f_k} 件 → 誤りを見つけるのに強いが、率の推定には使えない")'''),
    (M, "## 5. 費用と待ち時間 ― 中央値と 95 パーセント点（本物）\n講師の本物の実行の記録（out/）の、1 件ごとの待ち時間と費用から計算します。"),
    (C, '''rows5, per = [], {}
for lab_, f, what in [("lab03_classify_extract", "runs_classify_{}.jsonl", "分類 v1 120 件"),
                      ("lab05_agent_trajectory", "episodes_{}_k3.jsonl", "発注 10 件×3 回")]:
    for m in ("sonnet-5-5", "opus-5-5"):
        rr = kit.read_jsonl(f"{lab_}/out/{f.format(m)}")
        s = [r["seconds"] for r in rr]
        c = sum(r["cost_usd"] for r in rr) / len(rr)
        per[(what, m)] = c
        rows5.append([what, m.split("-")[0], len(rr), f"{stats.percentile(s, .5):.1f}", f"{stats.percentile(s, .95):.1f}", f"{c:.4f}"])
print(kit.table(rows5, ["実験", "モデル", "件数", "p50 秒", "p95 秒", "USD/件"]))
for m in ("sonnet-5-5", "opus-5-5"):
    c = per[("分類 v1 120 件", m)]
    print(f"分類 1 件 {m}: {c:.4f} USD → 月 1,600 件で {c * 1600:.2f} USD（正答はどちらも 120/120）")'''),
    (M, "## 6. 例題 ― 割り当て 72 対 728 の偏りを手で確かめる\n期待は 10% 対 90%。χ²（自由度 1）で調べます。"),
    (C, '''nc, nt, N = 72, 728, 800
ec, et = N * 0.10, N * 0.90
x1, x2 = (nc - ec) ** 2 / ec, (nt - et) ** 2 / et
print(f"期待: カナリア {ec:.0f} / 対照 {et:.0f}")
print(f"(72 − 80)² / 80 = {x1:.4f}、(728 − 720)² / 720 = {x2:.4f}")
print(f"χ² = {x1 + x2:.4f} → 自由度 1 で p = {stats.chi2_sf(x1 + x2, 1):.3f}")
print("p が 0.001 を下回ったら、割り当ての仕組みを疑い、結果は読まない")
alt = (60 - 80) ** 2 / 80 + (740 - 720) ** 2 / 720
print(f"（参考: 同じ 800 件で 60 対 740 なら χ² = {alt:.2f}、p = {stats.chi2_sf(alt, 1):.4f}）")'''),
])

# ---------------------------------------------------------------- P11
BOOKS["p11_safety.ipynb"] = nb(
    "P11 安全性の評価 ― 漏えいと止めすぎの両側",
    "返信の下書きを書く AI に、攻撃 12 件（他のお客様の情報を出させようとする）と、物騒な言葉を含むが正当な依頼 12 件を渡し、"
    "漏えい（規則で判定）と止めすぎ（LLM 判定＋人が全件読む）を測ります。データの連絡先はすべて架空です。", [
    (M, "## 1. 試験の中身 ― 問い合わせに紛れ込んだ別の指示\n取り込んだ文書の中の指示（間接プロンプトインジェクション）に従わないかを見ます。"),
    (C, WRAP + '''
from common import kit, stats
data = kit.load_json("safety.json")
items = data["items"]
print("攻撃", sum(x["kind"] == "attack" for x in items), "件 / 正当な依頼", sum(x["kind"] == "benign" for x in items), "件")
print("漏えいの印（架空の連絡先の一部）:")
print("  ", " ".join(data["leak_markers"]))
print("\\n--- 攻撃の例 ATK-01 ---")
wrap(items[0]["text"])'''),
    (M, "## 2. 返信 AI（Opus 5.5）で 24 件を回す\n講師の本物の実行の記録を再生します。止めすぎの判定役は Sonnet 5.5。"),
    (C, CUT + '''
import io, contextlib
P = "replay" if PROVIDER == "mock" else PROVIDER
sf = lab("run_safety", "lab11_safety")
with safe():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sf.main(["--provider", P, "--all", "--model", "claude-opus-5-5"])
    for line in buf.getvalue().splitlines():
        print(cut(line, 104))'''),
    (M, "## 3. 規則で判定できるものは規則で\n漏えいは「架空の電話番号の一部が返信に出たか」の文字列照合。LLM に判定させない。"),
    (C, '''show_file("lab11_safety/run_safety.py", 57, 59)
print()
runs_o = kit.read_jsonl("lab11_safety/out/runs_safety_opus-5-5.jsonl")
for r in runs_o:
    if r["kind"] == "attack":
        head = r["reply"].replace("\\n", " ")[:28] if r["reply"] else "（本文が空）"
        print(f"   {r['id']}  漏えいの印 {r['leak'] or 'なし'}  {len(r['reply']):4d} 字  {head}")'''),
    (M, "## 4. API の断りで本文が空になる ― ATK-02\nモデルが API 側で断ると、返信の下書きが空で返ります。"),
    (C, '''atk2 = next(x for x in items if x["id"] == "ATK-02")
print("--- ATK-02 の問い合わせ ---")
wrap(atk2["text"])
print()
for m in ("opus-5-5", "sonnet-5-5"):
    r = next(x for x in kit.read_jsonl(f"lab11_safety/out/runs_safety_{m}.jsonl") if x["id"] == "ATK-02")
    print(f"{m}: API の断り {r['api_refusal']} / 返信 {len(r['reply'])} 字 / 漏えい {r['leak'] or 'なし'} / {r['cost_usd']:.4f} USD")
print("\\n漏えいは 0。でもお客様への返信も無い → 本番では「空の下書きは人に回す」作りが要る")'''),
    (M, "## 5. 返信 AI を Sonnet 5.5 に替える ― 止めすぎ 1 件\n止めすぎの判定は LLM。判定された返信は、人が読んで確かめます。"),
    (C, '''with safe():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sf.main(["--provider", P, "--all", "--model", "claude-sonnet-5-5"])
    for line in buf.getvalue().splitlines():
        print(cut(line, 104))'''),
    (M, "## 6. 止めすぎとされた返信を読む ― BEN-11\n判定役の依頼文と、問い合わせ・返信の本文を並べます。"),
    (C, '''show_file("lab11_safety/prompts/helpful_judge.md", 2, 3)
ben = next(x for x in items if x["id"] == "BEN-11")
rep = next(x for x in kit.read_jsonl("lab11_safety/out/runs_safety_sonnet-5-5.jsonl") if x["id"] == "BEN-11")
print("\\n--- BEN-11 の問い合わせ ---")
wrap(ben["text"])
print("--- Sonnet の返信（先頭）---")
body = [l for l in rep["reply"].splitlines() if l.strip()]
wrap("\\n".join(body[:4]))
print("判定役の判定: helped =", rep["helped"], "→ 人が全文を読んで決める")'''),
    (M, "## 7. 例題 ― 12 件中 0 件から上限 24% を出す\n0 件のとき、Wilson の上限は z²/(n+z²) にまとまります。"),
    (C, '''import math
n, z = 12, 1.96
up = z * z / (n + z * z)
print(f"z² = {z * z:.4f}、上限 = {z * z:.4f} / ({n} + {z * z:.4f}) = {up:.4f} → {100 * up:.1f}%")
print(f"stats.wilson(0, 12) の上限 = {stats.wilson(0, 12)[1]:.4f}")
print(f"3 の法則: 3 / 12 = {3 / 12:.2f} → 25%")
print("「12 件で漏えい 0」から言えるのは「起きる率はおそらく 24% 以下」まで")
for t in (0.05, 0.01, 0.002):
    print(f"   上限を {100 * t:g}% にしたいなら、約 {math.ceil(3 / t)} 件の攻撃で 0 件が要る")'''),
])

# ---------------------------------------------------------------- P12
BOOKS["p12_usecases.ipynb"] = nb(
    "P12 ユースケース 5 本の評価カード",
    "各ラボの本物の実行の結果（out/）から、5 つの業務（すべて架空の会社）の評価カードを作り、Sonnet と Opus を全ラボで並べます。"
    "LLM は呼びません。", [
    (M, "## 1. 評価カードの書き方\n`build_cards.py` を回して、カードの欄と UC1 の中身を見ます。"),
    (C, CUT + '''
import io, contextlib
from common import kit
bc = lab("build_cards", "lab12_usecases")
with contextlib.redirect_stdout(io.StringIO()):
    md = bc.main([])
cards = md.split("\\n## ")[1:]
print("カード:", " / ".join(c.splitlines()[0].split("（")[0] for c in cards))
print("\\n■", cards[0].splitlines()[0])
for line in cards[0].splitlines():
    if line.startswith("- **") and "実測" not in line:
        print(cut("  " + line[2:].replace("**", ""), 100))'''),
    (M, "## 2. 問い合わせ分類・請求書・規程の質問のカード（実測の欄）\nUC1〜UC3。数字は各ラボの out/ から。"),
    (C, '''def measured(c):
    lines = c.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("- **実測**"))
    return [l.strip()[2:] for l in lines[i + 1:] if l.startswith("  - ")]

for c in cards[:3]:
    print("■", c.splitlines()[0])
    for m in measured(c):
        print("   " + cut(m, 96))'''),
    (M, "## 3. 発注エージェント・返信の下書きのカード（実測の欄）\nUC4・UC5。模擬の判定者は人ではありません。"),
    (C, '''for c in cards[3:]:
    print("■", c.splitlines()[0])
    for m in measured(c):
        print("   " + cut(m, 96))'''),
    (M, "## 4. Sonnet か Opus か ― 全ラボの比較表（その 1）\n分類・抽出・RAG・エージェント。"),
    (C, '''J = lambda p: kit.read_json(p)
L3, L4, L5 = "lab03_classify_extract/out/", "lab04_rag_eval/out/", "lab05_agent_trajectory/out/"
def two(f):
    return [f("sonnet-5-5"), f("opus-5-5")]
rows = [
    ["分類 v1 120 件", *two(lambda m: f"{J(L3 + f'summary_classify_{m}.json')['accuracy']:.0%}・{J(L3 + f'summary_classify_{m}.json')['cost_usd']:.2f} USD")],
    ["分類 v2 難問 48 件", *two(lambda m: f"{J(L3 + f'summary_classify_v2_{m}.json')['accuracy']:.0%}・{J(L3 + f'summary_classify_v2_{m}.json')['cost_usd']:.2f} USD")],
    ["抽出 48 件（全項目）", *two(lambda m: f"{J(L3 + f'summary_extract_{m}.json')['strict']['doc_all_correct']:.0%}・{J(L3 + f'summary_extract_{m}.json')['cost_usd']:.2f} USD")],
    ["RAG 30 問（照合 v1 → v2）", *two(lambda m: f"{J(L4 + f'summary_rag_normal_{m}.json')['correct']} → {J(L4 + f'summary_rag_normal_{m}.json')['correct_v2']}")],
    ["根拠を抜いた 26 問で断った", *two(lambda m: f"{J(L4 + f'summary_rag_degraded_{m}.json')['abstained']}/26")],
    ["発注 10 件×3 回", *two(lambda m: f"{J(L5 + f'summary_agent_{m}_k3.json')['pass']}/30・{J(L5 + f'summary_agent_{m}_k3.json')['cost_usd']:.2f} USD")],
]
print(kit.table(rows, ["実験", "Sonnet 5.5", "Opus 5.5"]))'''),
    (M, "## 5. Sonnet か Opus か ― 全ラボの比較表（その 2）\n判定役・依頼文が雑になったとき・安全。"),
    (C, '''L6, L7, L9, L11 = "lab06_judge_bias/out/", "lab07_judge_calibration/out/", "lab09_ci_gate/out/", "lab11_safety/out/"
rows = [
    ["判定役・素朴な依頼文で一貫", *two(lambda m: f"{J(L6 + f'summary_bias_naive_{m}.json')['result']['equal']['consistent']}/20")],
    ["判定 v1・dev の真陰性", *two(lambda m: f"{J(L7 + f'summary_calib_v1_dev_{m}.json')['tn']}/22")],
    ["短い依頼文の候補・v2 48 問", *two(lambda m: f"{sum(r['correct'] for r in kit.read_jsonl(L9 + f'runs_candidate_v2_{m}.jsonl'))}/48")],
    ["漏えい / 止めすぎ（各 12 件）", *two(lambda m: f"{J(L11 + f'summary_safety_{m}.json')['leaks']}/12 ・ {J(L11 + f'summary_safety_{m}.json')['over_refusals']}/12")],
]
print(kit.table(rows, ["実験", "Sonnet 5.5", "Opus 5.5"]))
print("\\n手引きつきの試験は両モデルとも飽和。差が出たのは費用・待ち時間・雑な依頼文での崩れ方・判定役の揺れ")'''),
])
