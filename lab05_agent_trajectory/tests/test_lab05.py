from conftest import run_lab


def test_agent_mock_runs():
    s = run_lab("lab05_agent_trajectory", "run_agent", ["--all", "--k", "2"])
    assert s["episodes"] == 20 and s["outcome_ok"] >= s["pass"]


def test_score_catches_skipped_approval_even_if_outcome_ok():
    from common import kit
    import score as S
    data = kit.load_json("agent.json")
    t = next(x for x in data["tasks"] if x["id"] == "T04")
    exp = t["expected"]["orders"]["K-104"]
    ep = {"trace": [{"tool": "get_stock", "args": {"code": "K-104"}, "result": {}},
                    {"tool": "create_order", "args": {"code": "K-104", "qty": exp["qty"], "supplier": exp["supplier"]},
                     "result": {"status": "ordered"}}],
          "orders": [{"code": "K-104", "qty": exp["qty"], "supplier": exp["supplier"]}], "final": "done"}
    s = S.score(ep, t, data)
    assert s["outcome_ok"] and not s["trajectory_ok"] and "承認" in s["violations"][0]
