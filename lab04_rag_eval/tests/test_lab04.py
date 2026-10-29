from conftest import run_lab


def test_rag_mock_runs_and_retrieval_metrics():
    r = run_lab("lab04_rag_eval", "run_rag", ["--all"])
    assert r["n"] == 30 and r["retrieval"]["recall@3"] > 0.8
    d = run_lab("lab04_rag_eval", "run_rag", ["--all", "--condition", "degraded", "--judge"])
    assert d["n"] == 26


def test_checker_v2_fixes_partial_abstain_and_alias():
    import run_rag as R
    ab = "規程に記載がありません"
    q11 = {"kind": "single", "must": [["事前"], ["部長"]]}
    ans = "会食の前に部長の承認を得てください [D08]。"
    assert R.check_answer(ans, q11, ab)["correct"] is False
    assert R.check_answer_v2(ans, q11, ab)["correct_v2"] is True
    q = {"kind": "single", "must": [["購買委員会"]]}
    ans2 = "購買委員会の承認が要ります [D07]。なお、相見積もりの要否は規程に記載がありません。"
    assert R.check_answer(ans2, q, ab)["correct"] is False and R.check_answer_v2(ans2, q, ab)["correct_v2"] is True
