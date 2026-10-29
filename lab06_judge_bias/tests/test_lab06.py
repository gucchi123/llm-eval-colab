from conftest import run_lab


def test_bias_mock_detects_built_in_biases():
    r = run_lab("lab06_judge_bias", "run_bias", ["--all"])
    assert set(r) == {"equal", "length", "long_wrong"}
    assert r["equal"]["first_pos_rate"] > 0.5          # 模擬の判定役には先に出た方へのひいきを入れてある


def test_selfpref_mock_runs():
    r = run_lab("lab06_judge_bias", "run_selfpref", ["--limit", "3"])
    assert r["n"] == 3 and set(r["judges"]) == {"claude-opus-5-5", "claude-sonnet-5-5"}
