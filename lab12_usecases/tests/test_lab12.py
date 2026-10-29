from conftest import run_lab


def test_cards_have_five_usecases():
    md = run_lab("lab12_usecases", "build_cards")
    assert md.count("## UC") == 5 and "架空" in md
