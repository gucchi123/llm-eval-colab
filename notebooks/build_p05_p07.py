"""P5〜P7 のノートブック。部品は _nbkit.py、全体は build_notebooks.py。

🔴 P5 の「模擬で崩れ方を見る」は mock（決まった筋書き）。数字は性能の証拠にしない。
🔴 P7 の評価者 A・B・C（lab07-2）と判定者 4 人（lab07-3）は模擬。人ではない。
"""
from _nbkit import C, M, nb

BOOKS = {}

# ---------------------------------------------------------------- P5
BOOKS["p05_agent_trajectory.ipynb"] = nb(
    "P5 エージェントを結果と軌跡で測る",
    "クロツグ食品（架空）の発注エージェントを、素の SDK の道具呼び出しループで動かし、"
    "発注の中身（結果）と、道具の呼び方（軌跡）の両方で採点します。", [
    (M, "## 画面に収める小さな道具\n長い行を画面の幅で折り返して表示するだけの関数です（中身は変えません）。"),
    (C, '''import io, contextlib
def fit(fn, *a, w=104, **k):   # fn の表示を、全角 2・半角 1 で数えた幅 w で折り返す
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **k)
    for line in buf.getvalue().splitlines():
        out, n = "", 0
        for ch in line:
            d = 2 if ord(ch) > 0x2E80 else 1
            if n + d > w:
                print(out)
                out, n = "        ", 8
            out, n = out + ch, n + d
        print(out)'''),
    (M, "## 1. 発注の手引きと、エージェントが使える道具\n手引きは `data/agent.json`、道具は `lab05_agent_trajectory/env.py` の本物です。"),
    (C, '''from common import kit, llm as L, metrics as M, stats
ag = lab("agent", "lab05_agent_trajectory")
from env import TOOLS
data = kit.load_json("agent.json")
fit(print, data["rules"].strip())
print("\\n道具:", " / ".join(t["name"] for t in TOOLS))
print("依頼:", len(data["tasks"]), "件。例", data["tasks"][3]["id"], data["tasks"][3]["request"])'''),
    (M, "## 2. 依頼 T04 を 1 回動かし、軌跡を見る\nOpus 5.5 の本物の応答を記録から再生します（費用 0、費用と待ち時間は元の実行の値）。"),
    (C, '''P = "replay" if PROVIDER == "mock" else PROVIDER
t04 = next(t for t in data["tasks"] if t["id"] == "T04")
with safe():
    ep = ag.run_episode(t04, data, provider=P, model="claude-opus-5-5", trial=0)
    for i, s in enumerate(ep["trace"], 1):
        print(f"{i}. {s['tool']}({', '.join(f'{k}={v}' for k, v in s['args'].items())})")
        print(f"     → {str(s['result'])[:86]}")
    print("発注:", ep["orders"])
    print(f"往復 {ep['turns']} 回 / 元の費用 {ep['cost_usd']:.4f} USD / {ep['seconds']:.1f} 秒")'''),
    (M, "## 3. 採点のコード ― 結果と軌跡を別々に見る\n`lab05_agent_trajectory/score.py` の本物です。発注の中身が合っていても、手順の違反があれば不合格にします。"),
    (C, '''sc = lab("score", "lab05_agent_trajectory")
fit(show, sc.score, 1, 20)'''),
    (M, "## 4. T04 を採点し、承認を抜いた軌跡と比べる\n本物の軌跡から request_approval だけを取り除いた写しを作り、同じ採点にかけます。"),
    (C, '''import copy
def brief(s):
    return f"結果 {'○' if s['outcome_ok'] else '×'} / 軌跡 {'○' if s['trajectory_ok'] else '×'} / 合格 {s['pass']} / 道具 {s['tool_calls']} 回"
print("本物の軌跡      :", brief(sc.score(ep, t04, data)))
bad = copy.deepcopy(ep)
bad["trace"] = [s for s in bad["trace"] if s["tool"] != "request_approval"]
s2 = sc.score(bad, t04, data)
print("承認を抜いた写し:", brief(s2))
print("   違反:", s2["violations"])'''),
    (M, "## 5. サイコロで考える ― 1 回でも当たるか、毎回当たるか\n1〜4 の目を「成功」（2/3）とし、3 回振るのを 1 万回くり返します。"),
    (C, '''import random
rng = random.Random(1)
trials = [[rng.randint(1, 6) <= 4 for _ in range(3)] for _ in range(10000)]
any3 = sum(any(t) for t in trials) / len(trials)
all3 = sum(all(t) for t in trials) / len(trials)
print(f"1 回の成功率 2/3 = {2 / 3:.3f}")
print(f"3 回のうち 1 回でも成功: サイコロ 1 万回 {any3:.3f} / 式 1-(1/3)^3 = {1 - (1 / 3) ** 3:.3f}")
print(f"3 回とも成功          : サイコロ 1 万回 {all3:.3f} / 式 (2/3)^3   = {(2 / 3) ** 3:.3f}")'''),
    (M, "## 6. pass@k と pass^k の式\n`common/metrics.py` の本物です。pass@k は Chen et al. 2021 の不偏推定、pass^k は τ-bench の「k 回とも成功」。"),
    (C, '''fit(show, M.pass_at_k)
print()
fit(show, M.pass_hat_k)'''),
    (M, "## 7. 3 回試したときの成功回数ごとに、二つの指標を並べる"),
    (C, '''rows = []
for c in range(4):
    rows.append([f"{c}/3", f"{M.pass_at_k(3, c, 1):.2f}", f"{M.pass_at_k(3, c, 2):.2f}", f"{M.pass_hat_k(3, c, 2):.2f}",
                 f"{M.pass_at_k(3, c, 3):.2f}", f"{M.pass_hat_k(3, c, 3):.2f}"])
print(kit.table(rows, ["成功", "pass@1", "pass@2", "pass^2", "pass@3", "pass^3"]))
print("本物の実行（10 件 × 3 回）は、Sonnet も Opus も全部の依頼が 3/3 → pass@3 も pass^3 も 1.00")'''),
    (M, "## 8. 10 件 × 3 回を 2 つのモデルで ― 合格・道具の数・費用・待ち時間\n講師が API で回した 60 回の記録を再生します。"),
    (C, '''by = {t["id"]: t for t in data["tasks"]}
best = sum(sc.minimal_calls(t) for t in data["tasks"]) * 3
EPS = {}
for model in ("claude-sonnet-5-5", "claude-opus-5-5"):
    with safe():
        eps = EPS[model] = [ag.run_episode(t, data, provider=P, model=model, trial=k) for t in data["tasks"] for k in range(3)]
        sco = [sc.score(e, by[e["task"]], data) for e in eps]
        c = {t: sum(s["pass"] for e, s in zip(eps, sco) if e["task"] == t) for t in by}
        cost, secs = sum(e["cost_usd"] for e in eps), [e["seconds"] for e in eps]
        print(f"{model:<18} 合格 {sum(s['pass'] for s in sco)}/{len(eps)}  pass^3 {sum(M.pass_hat_k(3, v, 3) for v in c.values()) / len(c):.2f}"
              f"  道具 {sum(s['tool_calls'] for s in sco)} 回（最短 {best}）")
        print(f"{'':<18} 費用 {cost:.4f} USD・1 回 {cost / len(eps):.4f}  待ち時間 p50 {stats.percentile(secs, .5):.1f}s"
              f" p95 {stats.percentile(secs, .95):.1f}s")'''),
    (M, "## 9. 依頼ごとの道具の数 ― 最短より多く呼んでいる"),
    (C, '''rows = []
for t in data["tasks"]:
    avg = {m: sum(len(e["trace"]) for e in EPS.get(m, []) if e["task"] == t["id"]) / 3 for m in EPS}
    rows.append([t["id"], sc.minimal_calls(t)] + [f"{avg[m]:.1f}" for m in EPS] + [t["request"][:24]])
print(kit.table(rows, ["依頼", "最短", "Sonnet", "Opus", "依頼の頭"]))'''),
    (M, "## 10. 失敗 0 件の読み方 ― 30 回中 0 回でも、失敗率の上限は 0 ではない"),
    (C, '''lo, hi = stats.wilson(30, 30)
print(f"30 回中 30 回合格 → 合格率の 95% 区間 [{100 * lo:.1f}, {100 * hi:.1f}]")
print(f"   → 失敗率の上限 {100 * (1 - lo):.1f}%（3 の法則なら 3/30 = {100 * stats.rule_of_three(30):.1f}%）")
for n in (100, 300, 1000):
    print(f"{n:>5} 回中 0 回の失敗なら、上限 {100 * (1 - stats.wilson(n, n)[0]):.1f}%")'''),
    (M, "## 11. 模擬（mock）で崩れ方を見る\n🔴 ここは模擬です。決まった筋書きで、腕前の確率で承認を飛ばしたり期限を見落としたりします。数字は性能の証拠になりません。"),
    (C, '''ra = lab("run_agent", "lab05_agent_trajectory")
print("🔴 模擬（mock）の結果。本物のモデルの性能ではありません")
with L.mock_handler(ra.mock_for(data)):
    for model in ("claude-sonnet-5-5", "claude-haiku-4-5"):
        eps = [ag.run_episode(t, data, provider="mock", model=model, trial=k) for t in data["tasks"] for k in range(3)]
        sco = [sc.score(e, by[e["task"]], data) for e in eps]
        c = {t: sum(s["pass"] for e, s in zip(eps, sco) if e["task"] == t) for t in by}
        print(f"模擬 {model}: 合格 {sum(c.values())}/30  pass@3 {sum(M.pass_at_k(3, v, 3) for v in c.values()) / 10:.2f}"
              f"  pass^3 {sum(M.pass_hat_k(3, v, 3) for v in c.values()) / 10:.2f}  結果だけ合格 "
              f"{sum(s['outcome_ok'] and not s['trajectory_ok'] for s in sco)}")
        for e, s in zip(eps, sco):
            if not s["pass"]:
                print(f"   {e['task']} {e['trial'] + 1} 回目: {(s['violations'] or ['発注の中身が違う'])[0]}")'''),
    (M, "## 12. 例題 ― 3 回中 2 回成功のとき、二つの指標を手で出す"),
    (C, '''from math import comb
n, c = 3, 2
print(f"pass@1 = 1 - C(1,1)/C(3,1) = 1 - {comb(1, 1)}/{comb(3, 1)} = {1 - comb(1, 1) / comb(3, 1):.3f}   関数 {M.pass_at_k(n, c, 1):.3f}")
print(f"pass@2 = 1 - C(1,2)/C(3,2) = 1 - {comb(1, 2)}/{comb(3, 2)} = {1 - comb(1, 2) / comb(3, 2):.3f}   関数 {M.pass_at_k(n, c, 2):.3f}")
print(f"pass^2 = C(2,2)/C(3,2) = {comb(2, 2)}/{comb(3, 2)} = {comb(2, 2) / comb(3, 2):.3f}       関数 {M.pass_hat_k(n, c, 2):.3f}")
print(f"pass@3 = 1 - C(1,3)/C(3,3) = 1 - {comb(1, 3)}/{comb(3, 3)} = {1 - comb(1, 3) / comb(3, 3):.3f}   関数 {M.pass_at_k(n, c, 3):.3f}")
print(f"pass^3 = C(2,3)/C(3,3) = {comb(2, 3)}/{comb(3, 3)} = {comb(2, 3) / comb(3, 3):.3f}       関数 {M.pass_hat_k(n, c, 3):.3f}")
print(f"1 回の成功率を 2/3 とみなすと: 3 回のうち 1 回でも {1 - (1 / 3) ** 3:.3f} / 3 回とも {(2 / 3) ** 3:.3f}")'''),
])

# ---------------------------------------------------------------- P6
BOOKS["p06_judge_bias.ipynb"] = nb(
    "P6 LLM 判定の偏りを測る",
    "ソラハ電機（架空）の返信の下書きを 2 本ずつ比べさせ、判定役の位置・長さ・自分びいきの偏りを測ります。"
    "判定役は主に Sonnet 5.5、比較に Opus 5.5。", [
    (M, "## 画面に収める小さな道具\n長い行を画面の幅で折り返して表示するだけの関数です（中身は変えません）。"),
    (C, '''import io, contextlib
def fit(fn, *a, w=104, **k):   # fn の表示を、全角 2・半角 1 で数えた幅 w で折り返す
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **k)
    for line in buf.getvalue().splitlines():
        out, n = "", 0
        for ch in line:
            d = 2 if ord(ch) > 0x2E80 else 1
            if n + d > w:
                print(out)
                out, n = "        ", 8
            out, n = out + ch, n + d
        print(out)'''),
    (M, "## 1. 入れ替えて 2 回聞くコード\n`common/judge.py` の本物です。順番を入れ替えて結論が変わったら引き分けにします（Wang et al. 2023 の考え方）。"),
    (C, '''from common import kit, llm as L, judge as J, stats
fit(show, J.pairwise)'''),
    (M, "## 2. 素朴な依頼文で、同じ質の組 EQ-13 を 2 回判定する\n判定役は Sonnet 5.5（記録の再生）。中身が同じで言い回しだけ違う 2 本の返信です。"),
    (C, '''P = "replay" if PROVIDER == "mock" else PROVIDER
naive = J.load_prompt("lab06_judge_bias/prompts/pairwise_naive.md")
x = next(p for p in kit.load_jsonl("pairs.jsonl") if p["id"] == "EQ-13")
with safe():
    v = J.pairwise(naive, f"受付日: {x['received']}\\n{x['inquiry']}", x["a"], x["b"], provider=P, model="claude-sonnet-5-5")
    print("1 回目（返信 x が A・返信 y が B）→ 勝ち:", v["first_order"])
    print("2 回目（返信 y が A・返信 x が B）→ 勝ち:", v["swapped"])
    print("先に出た方が勝ったか:", v["first_pos_won"], "/ 入れ替えても同じ結論:", v["consistent"], "→ 最終:", v["final"])'''),
    (M, "## 3. 素朴な依頼文で 20 組 × 2 回 ― Sonnet と Opus\n`run_bias.py` の本物を回し、位置の結果だけを短く表示します。"),
    (C, '''import io, contextlib
rb = lab("run_bias", "lab06_judge_bias")
def bias(model, prompt, kinds):
    with contextlib.redirect_stdout(io.StringIO()):
        return rb.main(["--provider", P, "--model", model, "--prompt", prompt, "--kinds", kinds, "--all"])
for model in ("claude-sonnet-5-5", "claude-opus-5-5"):
    with safe():
        e = bias(model, "naive", "equal,length")["equal"]
        print(f"{model:<18} 入れ替えても同じ結論 {e['consistent']}/{e['pairs']}  最終の引き分け {e['final']['tie']}/{e['pairs']}"
              f"  先に出た方の勝ち {e['first_pos_wins']}/{e['decided']}")'''),
    (M, "## 4. 依頼文に基準を書く\n素朴な依頼文（上）と、基準つきの依頼文（下）。`lab06_judge_bias/prompts/` の本物です。"),
    (C, '''show_file("lab06_judge_bias/prompts/pairwise_naive.md", 1, 1)
print()
fit(show_file, "lab06_judge_bias/prompts/pairwise.md", 1, 15)'''),
    (M, "## 5. 基準つきの依頼文で、同じ質の 20 組を判定する"),
    (C, '''for model, kinds in (("claude-sonnet-5-5", "equal,length,long_wrong"), ("claude-opus-5-5", "equal")):
    with safe():
        e = bias(model, "careful", kinds)["equal"]
        print(f"{model:<18} 入れ替えても同じ結論 {e['consistent']}/{e['pairs']}  最終の引き分け {e['final']['tie']}/{e['pairs']}"
              f"  先に出た方の勝ち {e['first_pos_wins']}/{e['decided']}")'''),
    (M, "## 6. 長さの偏り ― 中身が同じで長いだけの組、長いが誤っている組\n教科書は「長い方をひいきする」と言いますが、向きは測るまでわかりません。"),
    (C, '''for model in ("claude-sonnet-5-5", "claude-opus-5-5"):
    with safe():
        e = bias(model, "naive", "equal,length")["length"]
        print(f"素朴  {model:<18} 長い方を選んだ {e['per_order_y']}/{e['judgments']} 回"
              f"  最終: 長い方 {e['final']['y']} / 短い方 {e['final']['x']} / 引き分け {e['final']['tie']}")
with safe():
    r = bias("claude-sonnet-5-5", "careful", "equal,length,long_wrong")
    e, w = r["length"], r["long_wrong"]
    print(f"基準つき Sonnet 5.5   長い方を選んだ {e['per_order_y']}/{e['judgments']} 回"
          f"  最終: 長い方 {e['final']['y']} / 短い方 {e['final']['x']} / 引き分け {e['final']['tie']}")
    print(f"基準つき Sonnet 5.5   長いが誤り {w['pairs']} 組: 短く正しい方 {w['final']['x']} / 長く誤った方 {w['final']['y']}")'''),
    (M, "## 7. 自分びいき ― 書き手 2 × 判定役 2、10 件\nOpus と Sonnet が同じ問い合わせに返信を書き、両方が判定役として比べます（入れ替えて 2 回ずつ）。"),
    (C, '''rs = lab("run_selfpref", "lab06_judge_bias")
with safe():
    with contextlib.redirect_stdout(io.StringIO()):
        r = rs.main(["--provider", P, "--limit", "10"])
    for jm, s in r["judges"].items():
        print(f"判定役 {jm:<18} Opus の返信の勝ち {s['opus_wins']:>2} / Sonnet の返信の勝ち {s['sonnet_wins']:>2}"
              f" / 引き分け {s['ties']:>2} → Opus の得点 {s['opus_score']:.2f}")
    print(f"自分びいきの目安 {r['self_pref']:+.2f}  問いごとの差の 95% 区間 [{r['diff_ci'][0]:+.2f}, {r['diff_ci'][1]:+.2f}]（n={r['n']}）")
    print("返信の平均の長さ: " + " / ".join(f"{w} {v:.0f} 字" for w, v in r["avg_len"].items()) + f" / 費用 {r['cost_usd']} USD")'''),
    (M, "## 8. 例題 ― 入れ替え 2 回の結果表を読む\n素朴な依頼文・Sonnet 5.5 の、同じ質の 20 組（上の 3 で書き出した本物の記録）。"),
    (C, '''from collections import Counter
runs = [r for r in kit.read_jsonl("lab06_judge_bias/out/runs_bias_naive_sonnet-5-5.jsonl") if r["kind"] == "equal"]
tab = Counter((r["first_order"], r["swapped"]) for r in runs)
ks = ["x", "y", "tie"]
print(kit.table([[f"1 回目 {a}"] + [tab[(a, b)] for b in ks] for a in ks], ["", "2 回目 x", "2 回目 y", "2 回目 tie"]))
print(f"対角（入れ替えても同じ）= {' + '.join(str(tab[(k, k)]) for k in ks)} = {sum(tab[(k, k)] for k in ks)}/{len(runs)}")
dec = [fp for r in runs for v, fp in zip((r["first_order"], r["swapped"]), r["first_pos_won"]) if v != "tie"]
print(f"勝ち負けを付けた {len(dec)} 回のうち、先に出た方の勝ち {sum(dec)} 回 = {kit.pct(sum(dec) / len(dec))}"
      f" 95%区間 {kit.ci_str(*stats.wilson(sum(dec), len(dec)))}")
print("最終（対角はそのまま、対角の外は引き分け）:", dict(Counter(r["final"] for r in runs)))'''),
])

# ---------------------------------------------------------------- P7
BOOKS["p07_judge_calibration.ipynb"] = nb(
    "P7 判定を人に合わせる",
    "返信の下書き 80 件（ソラハ電機・架空）に pass / fail を付ける判定役を、作った側のラベルに合わせて直します。"
    "🔴 評価者 A・B・C と判定者 4 人は**模擬**（人ではありません）。", [
    (M, "## 画面に収める小さな道具\n長い行を画面の幅で折り返して表示するだけの関数です（中身は変えません）。"),
    (C, '''import io, contextlib
def fit(fn, *a, w=104, **k):   # fn の表示を、全角 2・半角 1 で数えた幅 w で折り返す
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **k)
    for line in buf.getvalue().splitlines():
        out, n = "", 0
        for ch in line:
            d = 2 if ord(ch) > 0x2E80 else 1
            if n + d > w:
                print(out)
                out, n = "        ", 8
            out, n = out + ch, n + d
        print(out)'''),
    (M, "## 1. 返信 80 件と、判定させる関数\n依頼文は `lab07_judge_calibration/prompts/pointwise_v1.md`・`v2.md`。dev と test に分けてから使います。"),
    (C, '''from common import kit, llm as L, judge as J, agreement as A, stats
rc = lab("run_calibrate", "lab07_judge_calibration")
P = "replay" if PROVIDER == "mock" else PROVIDER
S, O = "claude-sonnet-5-5", "claude-opus-5-5"
reps, policy = kit.load_jsonl("replies.jsonl"), kit.load_text("reply_policy.md")
dev, test = rc.split(reps)
def judge_all(prompt, rows, model):
    t = J.load_prompt(f"lab07_judge_calibration/prompts/pointwise_{prompt}.md")
    return [J.pointwise(t, inquiry=r["inquiry"], reply=r["reply"], policy=policy, received=r["received"],
                        provider=P, model=model)[0] for r in rows]
print(f"返信 {len(reps)} 件 → dev {len(dev)} / test {len(test)}")'''),
    (M, "## 2. 依頼文 v1 で dev を判定する ― 真陽性率と真陰性率\nTPR = 不合格を不合格と見つけた率、TNR = 合格を合格とした率。"),
    (C, '''V1, truth = {}, [r["label"] for r in dev]
print(f"dev {len(dev)} 件: 不合格 {truth.count('fail')} / 合格 {truth.count('pass')}")
for model in (S, O):
    with safe():
        pred = V1[model] = judge_all("v1", dev, model)
        m = A.tpr_tnr(pred, truth, positive="fail")
        print(f"{model:<18} TPR {m['tp']}/{m['tp'] + m['fn']} = {kit.pct(m['tpr'])}  TNR {m['tn']}/{m['tn'] + m['fp']} = "
              f"{kit.pct(m['tnr'])}  κ {A.cohen_kappa(pred, truth):.3f}")'''),
    (M, "## 3. コインを投げても半分は一致する ― 偶然の一致を引いた一致\nでたらめに pass / fail を付ける 2 人を 1000 件ずつ作ります。"),
    (C, '''import random
rng = random.Random(0)
a = [rng.choice(["pass", "fail"]) for _ in range(1000)]
b = [rng.choice(["pass", "fail"]) for _ in range(1000)]
print(f"コイン 2 枚: 一致 {sum(x == y for x, y in zip(a, b)) / 1000:.3f} / κ {A.cohen_kappa(a, b):+.3f}")
c = ["pass" if rng.random() < .9 else "fail" for _ in range(1000)]
d = ["pass" if rng.random() < .9 else "fail" for _ in range(1000)]
print(f"9 割 pass と言うだけの 2 人: 一致 {sum(x == y for x, y in zip(c, d)) / 1000:.3f} / κ {A.cohen_kappa(c, d):+.3f}")'''),
    (M, "## 4. 調整用（dev）と試験用（test）に分けるコード\n欠陥の種類ごとに半分ずつ。乱数は固定。test は最後まで見ません。"),
    (C, '''show(rc.split)'''),
    (M, "## 5. 分けた結果 ― 欠陥の種類ごとの件数"),
    (C, '''from collections import Counter
cd, ct = Counter(r["defect"] or "(欠陥なし)" for r in dev), Counter(r["defect"] or "(欠陥なし)" for r in test)
print(kit.table([[k, cd[k], ct[k]] for k in sorted(cd | ct)], ["欠陥の種類", "dev", "test"]))
print("不合格: dev", sum(r["label"] == "fail" for r in dev), "/ test", sum(r["label"] == "fail" for r in test))'''),
    (M, "## 6. 依頼文 v1 と v2\nv2 は 4 つの点検と返信の決まりを書き足したもの（`lab07_judge_calibration/prompts/`）。"),
    (C, '''show_file("lab07_judge_calibration/prompts/pointwise_v1.md", 1, 1)
print()
fit(show_file, "lab07_judge_calibration/prompts/pointwise_v2.md", 1, 9)'''),
    (M, "## 7. 依頼文 v2 で dev を直し、test で 1 回だけ測る"),
    (C, '''V2 = {}
for name, rows in (("dev", dev), ("test", test)):
    truth = [r["label"] for r in rows]
    for model in (S, O):
        with safe():
            pred = V2[(name, model)] = judge_all("v2", rows, model)
            m = A.tpr_tnr(pred, truth, positive="fail")
            print(f"v2 {name:<4} {model:<18} TPR {m['tp']}/{m['tp'] + m['fn']}  TNR {m['tn']}/{m['tn'] + m['fp']}"
                  f"  κ {A.cohen_kappa(pred, truth):.3f}")'''),
    (M, "## 8. 判定が数えた不合格率を直す（Rogan-Gladen）\n校正は dev の TPR / TNR、直すのは test で判定が数えた率。区間はブートストラップ。"),
    (C, '''show(A.rogan_gladen)
cal, obs = V2[("dev", S)], V2[("test", S)]
m = A.tpr_tnr(cal, [r["label"] for r in dev], positive="fail")
p_obs = obs.count("fail") / len(obs)
print(f"\\n直した率 = ({p_obs:.3f} + {m['tnr']:.3f} - 1) / ({m['tpr']:.4f} + {m['tnr']:.3f} - 1)"
      f" = {A.rogan_gladen(p_obs, m['tpr'], m['tnr']):.3f}")
rg = A.corrected_prevalence_ci(cal, [r["label"] for r in dev], obs, positive="fail", seed=3)
print(f"判定が数えた {kit.pct(rg['observed'])} → 補正 {kit.pct(rg['corrected'])} 95%区間 {kit.ci_str(rg['lo'], rg['hi'])}"
      f"（本当の率 {kit.pct([r['label'] for r in test].count('fail') / len(test))}）")'''),
    (M, "## 9. 評価者どうしの一致 ― Cohen κ・Fleiss κ・Krippendorff α\n🔴 評価者 A・B・C は模擬（乱数のくせで作ったラベル）。人ではありません。"),
    (C, '''import itertools
R = ["A", "B", "C"]
lab_ = {k: [x["annotators"][k] for x in reps] for k in R}
rows = []
for a, b in itertools.combinations(R, 2):
    k = A.cohen_kappa(lab_[a], lab_[b])
    rows.append([f"模擬 {a}-{b}", kit.pct(sum(x == y for x, y in zip(lab_[a], lab_[b])) / len(reps)), f"{k:.3f}", A.landis_koch(k)])
print(kit.table(rows, ["組", "一致", "Cohen κ", "目安"]))
units = [[x["annotators"][k] for k in R] for x in reps]
print(f"\\n3 人: Fleiss κ = {A.fleiss_kappa(units):.3f} / Krippendorff α = {A.krippendorff_alpha(units):.3f}")
half = [[u[0], u[1], u[2] if i % 2 else None] for i, u in enumerate(units)]
print(f"C が半分しか付けていない場合の α = {A.krippendorff_alpha(half):.3f}（κ では計算できない形）")'''),
    (M, "## 10. LLM 判定と、模擬の評価者・作った側のラベル\nLLM 判定は上の 7 の Sonnet 5.5・依頼文 v2（dev＋test の 80 件）。"),
    (C, '''llm = dict(zip([r["id"] for r in dev + test], V2[("dev", S)] + V2[("test", S)]))
pred = [llm[x["id"]] for x in reps]
for k in R:
    print(f"LLM - 模擬 {k}  κ = {A.cohen_kappa(pred, lab_[k]):.3f}   /  作った側のラベル - 模擬 {k}  κ = "
          f"{A.cohen_kappa([x['label'] for x in reps], lab_[k]):.3f}")'''),
    (M, "## 11. 模擬の判定者とは ― LLM に人物像を与えたもの\n🔴 4 人とも Sonnet 5.5 に人物像とガイドラインを渡したもの。人ではありません。"),
    (C, '''rp = lab("run_personas", "lab07_judge_calibration")
plist = rp.personas()
for pid, txt in plist.items():
    lines = txt.splitlines()
    print(lines[0].lstrip("# "))
    fit(print, "   " + next(l for l in lines if l.startswith("くせ")))
print()
fit(show_file, "lab07_judge_calibration/prompts/annotate_batch.md", 1, 1)'''),
    (M, "## 12. ガイドライン v1 と v2\nv1 は要約だけの初版。v2 は公開の指針（特定商取引法の返品特約・ISO 10002・QA の評価項目）で書き直した版です。"),
    (C, '''fit(show_file, "lab07_judge_calibration/prompts/guideline_v1.md", 1, 9)'''),
    (M, "## 12-2. ガイドライン v2 の見出し ― 判定の順番・fail にしないもの・迷ったとき・改訂の記録・出典"),
    (C, '''fit(show_file, "lab07_judge_calibration/prompts/guideline_v2.md", grep="#")'''),
    (M, "## 13. 模擬の判定者 4 人が v1 と v2 で 80 件を判定する\n10 件ずつ・人ごとに読む順番を変えて判定します（記録の再生）。"),
    (C, '''args = kit.parser("demo").parse_args(["--provider", P, "--model", S])
LAB, pids = {}, sorted(plist)
for rnd in ("v1", "v2"):
    with safe():
        LAB[rnd], cost = rp.label_round(reps, rnd, args, plist)
        for name, rows in (("dev", dev), ("test", test), ("全 80", reps)):
            ids = [x["id"] for x in rows]
            fk = A.fleiss_kappa([[LAB[rnd][p][i]["verdict"] for p in pids] for i in ids])
            un = sum(len({LAB[rnd][p][i]["verdict"] for p in pids}) == 1 for i in ids)
            print(f"ガイドライン {rnd}  {name:<5} Fleiss κ {fk:.3f}  全員一致 {un}/{len(ids)}")
        print(f"   費用 {cost:.4f} USD")'''),
    (M, "## 14. 割れた返信を別のモデルが裁定する\nv2 で割れた返信だけを Opus 5.5 が裁定し、「裁定済みの基準」を作ります。"),
    (C, '''args.adj_model = O
with safe():
    adj = rp.adjudicate(LAB["v2"], reps, args, "lab07_judge_calibration/out")'''),
    (M, "## 15. test を裁定済みの基準で測り直す\n下がったように見えた κ は、作った側の正解ラベルの誤り（2 件）でした。"),
    (C, '''ref = kit.read_json("lab07_judge_calibration/out/adjudicated_reference.json")["reference"]
for model in (S, O):
    pred = V2[("test", model)]
    k0 = A.cohen_kappa(pred, [r["label"] for r in test])
    m = A.tpr_tnr(pred, [ref[r["id"]] for r in test], positive="fail")
    print(f"{model:<18} 作った側のラベルで κ {k0:.3f} → 裁定済みの基準で TPR {m['tp']}/{m['tp'] + m['fn']}"
          f"  TNR {m['tn']}/{m['tn'] + m['fp']}  κ {A.cohen_kappa(pred, [ref[r['id']] for r in test]):.3f}")'''),
    (M, "## 16. 例題 ― 2 行 2 列の表から κ を手で出す\n依頼文 v1・Sonnet 5.5・dev 38 件（上の 2 の本物の判定）。"),
    (C, '''pred, truth = V1[S], [r["label"] for r in dev]
m = A.tpr_tnr(pred, truth, positive="fail")
tp, fn, fp, tn, n = m["tp"], m["fn"], m["fp"], m["tn"], len(dev)
print(kit.table([["判定 fail", tp, fp], ["判定 pass", fn, tn]], ["", "正解 fail", "正解 pass"]))
po = (tp + tn) / n
pe = (tp + fp) / n * (tp + fn) / n + (fn + tn) / n * (fp + tn) / n
print(f"\\n一致 po = ({tp} + {tn}) / {n} = {po:.3f}")
print(f"偶然の一致 pe = {tp + fp}/{n} × {tp + fn}/{n} + {fn + tn}/{n} × {fp + tn}/{n} = {pe:.3f}")
print(f"κ = (po - pe) / (1 - pe) = {(po - pe) / (1 - pe):.3f}   関数 cohen_kappa {A.cohen_kappa(pred, truth):.3f}")'''),
    (M, "## 17. 例題 ― ガイドライン v1 で割れた dev の返信を読む\n割れたところが、ガイドラインの穴の候補です。"),
    (C, '''rows = []
for r in dev:
    vs = [LAB["v1"][p][r["id"]]["verdict"] for p in pids]
    if len(set(vs)) > 1:
        rows.append([r["id"], r["defect"] or "(欠陥なし)", r["label"], " ".join(f"{p[:2]}:{v}" for p, v in zip(pids, vs))])
print(kit.table(rows, ["返信", "作った欠陥", "正解", "模擬の判定者 4 人"]))
print(f"\\ndev {len(dev)} 件のうち、割れたのは {len(rows)} 件")'''),
    (M, "## 18. 割れたところをどう直したか ― v2 の改訂の記録"),
    (C, '''fit(show_file, "lab07_judge_calibration/prompts/guideline_v2.md", 48, 55)'''),
])
