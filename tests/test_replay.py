"""講師の記録（.cache/llm）を再生すると、out/ に残した本物の実行と同じ数字になるか。API は呼ばない（LLM_CACHE_ONLY=1）。
記録が無い配布直後の状態では飛ばす。
"""
import os

import pytest

from conftest import ROOT, run_lab
from common import kit

HAS = os.path.isdir(os.path.join(ROOT, ".cache", "llm")) and os.path.isdir(os.path.join(ROOT, "lab03_classify_extract", "out"))
pytestmark = pytest.mark.skipif(not HAS, reason="講師の記録が無い")


@pytest.fixture(autouse=True)
def _sep_out(monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_OUT_ROOT", str(tmp_path))


def _rec(lab, name):
    return kit.read_json(os.path.join(ROOT, lab, "out", name))


def test_replay_classify_matches_record():
    r = run_lab("lab03_classify_extract", "run_classify", ["--provider", "replay", "--all", "--model", "claude-opus-5-5"])
    rec = _rec("lab03_classify_extract", "summary_classify_opus-5-5.json")
    assert r["accuracy"] == rec["accuracy"] and abs(r["cost_usd"] - rec["cost_usd"]) < 1e-6


def test_replay_calibration_test_matches_record():
    r = run_lab("lab07_judge_calibration", "run_calibrate",
                ["--provider", "replay", "--model", "claude-sonnet-5-5", "--split", "test", "--prompt", "v2"])
    rec = _rec("lab07_judge_calibration", "summary_calib_v2_test_sonnet-5-5.json")
    assert (r["tp"], r["tn"], r["fp"], r["fn"]) == (rec["tp"], rec["tn"], rec["fp"], rec["fn"])


def test_replay_agent_matches_record():
    r = run_lab("lab05_agent_trajectory", "run_agent", ["--provider", "replay", "--all", "--k", "3", "--model", "claude-sonnet-5-5"])
    rec = _rec("lab05_agent_trajectory", "summary_agent_sonnet-5-5_k3.json")
    assert r["pass"] == rec["pass"] and r["outcome_ok"] == rec["outcome_ok"]
