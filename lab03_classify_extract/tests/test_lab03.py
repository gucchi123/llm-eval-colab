from conftest import run_lab


def test_classify_mock_v1_and_v2():
    r = run_lab("lab03_classify_extract", "run_classify", ["--all"])
    assert r["n"] == 120 and 0.5 < r["accuracy"] <= 1 and "weighted_accuracy" in r and "ece" in r
    r2 = run_lab("lab03_classify_extract", "run_classify", ["--all", "--set", "v2"])
    assert r2["n"] == 48 and "hard" in r2["by_difficulty"]


def test_extract_strict_vs_normalized():
    s = run_lab("lab03_classify_extract", "run_extract", ["--all"])
    assert s["normalized"]["doc_all_correct"] >= s["strict"]["doc_all_correct"]


def test_normalizer():
    import run_extract as E
    assert E.norm("claim_amount", "３０,０００円") == 30000
    assert E.norm("incident_date", "2026/9/2") == "2026-09-02"
    assert E.norm("claimant", "加賀谷 美咲") == "加賀谷美咲"
