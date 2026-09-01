from app.ingestion.vlr_stats import parse_duration


def test_parse_duration_minutes_and_seconds():
    assert parse_duration("45:20") == 2720


def test_parse_duration_hours_minutes_and_seconds():
    assert parse_duration("1:03:03") == 3783


def test_parse_duration_invalid_values():
    assert parse_duration(None) is None
    assert parse_duration("") is None
    assert parse_duration("unknown") is None
    assert parse_duration("1:bad:03") is None