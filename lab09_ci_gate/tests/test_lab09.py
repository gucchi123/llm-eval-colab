import os
import sys

from conftest import ROOT, run_lab

sys.path.insert(0, os.path.join(ROOT, "lab09_ci_gate"))


def test_gate_stops_regression_and_passes_identical():
    from common import kit
    import gate as G
    def mk(n):
        return {f"X{i}": {"id": f"X{i}", "correct": 1, "pred": "a", "scenario": "s" + str(i % 4), "cost_usd": 0} for i in range(n)}
    cfg = kit.read_json(os.path.join(ROOT, "lab09_ci_gate", "gate_config.json"))
    assert G.evaluate(mk(200), mk(200), cfg)["pass"] is True
    # 全く同じでも 40 件では「3 ポイント以内」と言えない（件数が足りない）→ 止める
    assert G.evaluate(mk(40), mk(40), cfg)["pass"] is False
    base = mk(200)
    worse = {k: {**v, "correct": 0 if v["scenario"] == "s0" else 1} for k, v in base.items()}
    r = G.evaluate(base, worse, cfg)
    assert r["pass"] is False and not r["checks"][1]["ok"]


def test_gate_end_to_end_mock():
    run_lab("lab03_classify_extract", "run_classify", ["--all", "--set", "v2"])
    run_lab("lab09_ci_gate", "run_candidate", ["--all"])
    import gate as G
    code = G.main(["--baseline", os.path.join(ROOT, "lab03_classify_extract", "out_mock", "runs_classify_v2_opus-5-5.jsonl"),
                   "--candidate", os.path.join(ROOT, "lab09_ci_gate", "out_mock", "runs_candidate_v2_opus-5-5.jsonl")])
    assert code in (0, 1)
