from d3xc.scrape.athletic_net import link_hs_mark, name_similarity


def test_name_similarity():
    assert name_similarity("Alex Miller", "Alex Miller") == 1.0
    assert name_similarity("Alex Miller", "Miller, Alex") > 0.9
    assert name_similarity("Alex Miller", "Jordan Davis") < 0.5


def test_link_confidence_gradyear_penalty():
    exact = link_hs_mark(
        "Alex Miller", "Alex Miller", college_team="Mount Union", gender="men",
        event="3200m", mark_seconds=560.0, hs_grad_year=2020, source="x",
        grad_year_hint=2020,
    )
    off = link_hs_mark(
        "Alex Miller", "Alex Miller", college_team="Mount Union", gender="men",
        event="3200m", mark_seconds=560.0, hs_grad_year=2017, source="x",
        grad_year_hint=2020,
    )
    assert exact.match_confidence == 1.0
    assert off.match_confidence < exact.match_confidence
