from conftest import run_lab


def test_stats_runs():
    r = run_lab("lab08_stats", "run_stats")
    assert r["paired"]["n"] > 0 and r["cluster"]["clustered"] > 0
