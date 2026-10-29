from conftest import run_lab


def test_online_simulation_deterministic():
    a = run_lab("lab10_online_eval", "run_online")
    b = run_lab("lab10_online_eval", "run_online")
    assert a["shadow"] == b["shadow"] and a["drift"]["p"] < 0.01 and a["review"]["risk_found"] >= a["review"]["random_found"]
