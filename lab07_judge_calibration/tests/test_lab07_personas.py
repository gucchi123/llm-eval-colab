from conftest import run_lab


def test_personas_mock_revision_raises_agreement_and_adjudicates():
    r = run_lab("lab07_judge_calibration", "run_personas", ["--adjudicate"])
    assert len(r["personas"]) == 4
    f1, f2 = r["rounds"]["v1"]["all"]["fleiss"], r["rounds"]["v2"]["all"]["fleiss"]
    assert f2 > f1                              # 模擬では v2 で一致が上がるように作ってある
    assert "adjudication" in r and r["adjudication"]["split"] >= 0


def test_guideline_v2_cites_sources():
    import os
    from conftest import ROOT
    g = open(os.path.join(ROOT, "lab07_judge_calibration", "prompts", "guideline_v2.md"), encoding="utf-8").read()
    for s in ("特定商取引法", "ISO 10002", "Zendesk", "COPC", "改訂の記録"):
        assert s in g
