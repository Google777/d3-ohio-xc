from d3xc.scrape.timeutil import seconds_to_time, time_to_seconds


def test_parse_mmss():
    assert time_to_seconds("24:33.4") == 24 * 60 + 33.4
    assert time_to_seconds("6:02.1") == 6 * 60 + 2.1


def test_parse_hms():
    assert time_to_seconds("1:02:33") == 3600 + 2 * 60 + 33


def test_parse_bad():
    for bad in ["", "DNF", "-", "NT", None]:
        assert time_to_seconds(bad) is None


def test_roundtrip():
    secs = 25 * 60 + 12.3
    assert time_to_seconds(seconds_to_time(secs)) == secs


def test_format_hour():
    assert seconds_to_time(3723.0).startswith("1:02:")
