from conftest import run_lab


def test_golden_reproducible_and_leak_found():
    s = run_lab("lab02_golden_set", "run_golden")
    assert s["reproducible"] is True
    assert sum(s["label_golden"].values()) == 120
    assert len(s["leaked_tests"]) >= 1          # 素朴に選んだお手本は試験と重なる（教材の狙い）
    assert s["clusters"] < 120
