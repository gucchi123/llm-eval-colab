"""共通部品（統計・一致度・指標・抜き取り）の自己検査。値は手計算・公開の例と照合。"""
import math

from common import agreement as A, metrics as M, stats as S
from common.sampling import leakage, stratified_sample


def test_wilson_known_values():
    lo, hi = S.wilson(0, 10)
    assert abs(lo) < 1e-12 and abs(hi - 0.2775) < 1e-3
    lo, hi = S.wilson(120, 120)
    assert abs(lo - 0.9690) < 1e-3 and hi == 1.0


def test_rule_of_three_close_to_wilson_upper():
    assert abs(S.rule_of_three(100) - 0.03) < 1e-9
    assert S.wilson(0, 100)[1] < 0.04


def test_mcnemar_exact():
    assert S.mcnemar_exact(0, 0) == 1.0
    assert abs(S.mcnemar_exact(14, 0) - 2 * 0.5 ** 14) < 1e-12
    assert abs(S.mcnemar_exact(3, 3) - 1.0) < 1e-12


def test_paired_bootstrap_and_permutation_detect_clear_difference():
    a = [1] * 40
    b = [1] * 25 + [0] * 15
    r = S.paired_bootstrap(a, b, seed=1)
    assert r["hi"] < 0 and abs(r["diff"] + 15 / 40) < 1e-12
    assert S.paired_permutation(a, b, B=2000, seed=1) < 0.01


def test_cluster_se_larger_when_clustered():
    xs = [1] * 8 + [0] * 8 + [1] * 8 + [0] * 8
    cl = ["a"] * 8 + ["b"] * 8 + ["c"] * 8 + ["d"] * 8
    assert S.cluster_se(xs, cl) > 2 * S.naive_se(xs)


def test_sample_sizes():
    assert S.n_for_margin(0.03, 0.5) == 1068
    assert S.n_paired(0.10, 0.2) < S.n_paired(0.05, 0.2)


def test_chi2_and_psi():
    assert abs(S.chi2_sf(3.841, 1) - 0.05) < 1e-3
    assert abs(S.chi2_sf(11.07, 5) - 0.05) < 1e-3
    assert S.psi({"a": 10, "b": 10}, {"a": 10, "b": 10}) == 0


def test_holm():
    out = S.holm({"x": 0.01, "y": 0.04, "z": 0.03})
    assert out == {"x": True, "y": False, "z": False}


def test_kappas():
    a = ["y"] * 20 + ["n"] * 15 + ["y"] * 5 + ["n"] * 10
    b = ["y"] * 20 + ["n"] * 15 + ["n"] * 5 + ["y"] * 10
    assert abs(A.cohen_kappa(a, b) - 0.4) < 1e-9          # Wikipedia の例（po=0.7, pe=0.5）
    assert A.cohen_kappa(["p", "f"], ["p", "f"]) == 1.0
    assert abs(A.krippendorff_alpha([["a", "a"], ["b", "b"], ["a", "a"]]) - 1.0) < 1e-12
    # 欠けがあっても計算できる
    assert not math.isnan(A.krippendorff_alpha([["a", "a", None], ["b", None, "b"], ["a", "b", "a"]]))
    assert abs(A.fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]]) - 1.0) < 1e-12


def test_tpr_tnr_and_rogan_gladen():
    m = A.tpr_tnr(["fail", "pass", "fail", "pass"], ["fail", "fail", "pass", "pass"])
    assert m["tpr"] == 0.5 and m["tnr"] == 0.5
    assert abs(A.rogan_gladen(0.4, 0.9, 0.95) - (0.4 + 0.95 - 1) / (0.9 + 0.95 - 1)) < 1e-12
    assert math.isnan(A.rogan_gladen(0.4, 0.5, 0.5))


def test_metrics():
    rep = M.classification_report(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
    assert abs(rep["accuracy"] - 2 / 3) < 1e-12 and abs(rep["per_class"]["a"]["recall"] - 0.5) < 1e-12
    assert M.recall_at_k(["d1", "d2"], {"d2"}, 1) == 0 and M.mrr(["d1", "d2"], {"d2"}) == 0.5
    assert abs(M.ndcg_at_k(["d2", "d1"], {"d2"}, 3) - 1.0) < 1e-12
    e, _ = M.ece([0.9, 0.9], [1, 0], bins=5)
    assert abs(e - 0.4) < 1e-12


def test_pass_at_k_and_pass_hat_k():
    assert M.pass_at_k(3, 1, 3) == 1.0 and M.pass_hat_k(3, 1, 3) == 0.0
    assert abs(M.pass_at_k(10, 3, 1) - 0.3) < 1e-12 and abs(M.pass_hat_k(10, 3, 1) - 0.3) < 1e-12
    assert abs(M.pass_hat_k(4, 2, 2) - 1 / 6) < 1e-12


def test_stratified_sample_keeps_small_strata_and_is_deterministic():
    rows = [{"id": f"r{i}", "g": "big" if i < 95 else "small"} for i in range(100)]
    s1 = stratified_sample(rows, key=lambda r: r["g"], n=20, min_per_stratum=3, seed=1)
    s2 = stratified_sample(rows, key=lambda r: r["g"], n=20, min_per_stratum=3, seed=1)
    assert [r["id"] for r in s1] == [r["id"] for r in s2] and len(s1) == 20
    assert sum(r["g"] == "small" for r in s1) >= 3


def test_leakage_finds_near_duplicates():
    t = [{"id": "t1", "text": "メールマガジンの配信を止めたいです。"}]
    s = [{"id": "s1", "text": "メールマガジンの配信を止めたいです。\nよろしくお願いいたします。"}]
    assert leakage(t, s)[0]["shot"] == "s1"
