from datetime import datetime, timezone

import pytest

from app.ingestion import vlr_upcoming


def make_match_data():
    return {
        "vlr_id": 123456,
        "team1": {
            "vlr_id": 1,
            "name": "Team One",
        },
        "team2": {
            "vlr_id": 2,
            "name": "Team Two",
        },
        "team1_score": 2,
        "team2_score": 1,
        "event_name": "Test Event",
        "stage": "Playoffs",
        "status": "completed",
        "scheduled_at": datetime.now(timezone.utc),
    }


def test_parse_upcoming_match_marks_match_scheduled(
    monkeypatch,
):
    data = make_match_data()

    monkeypatch.setattr(
        vlr_upcoming,
        "parse_completed_match",
        lambda client, match_card: data,
    )

    result = vlr_upcoming.parse_upcoming_match(
        None,
        None,
    )

    assert result["status"] == "scheduled"
    assert result["team1_score"] is None
    assert result["team2_score"] is None


def test_parse_upcoming_match_rejects_unknown_team(
    monkeypatch,
):
    data = make_match_data()
    data["team2"]["vlr_id"] = None

    monkeypatch.setattr(
        vlr_upcoming,
        "parse_completed_match",
        lambda client, match_card: data,
    )

    with pytest.raises(
        vlr_upcoming.MatchNotForecastableError
    ):
        vlr_upcoming.parse_upcoming_match(
            None,
            None,
        )


def test_parse_upcoming_match_rejects_unknown_time(
    monkeypatch,
):
    data = make_match_data()
    data["scheduled_at"] = None

    monkeypatch.setattr(
        vlr_upcoming,
        "parse_completed_match",
        lambda client, match_card: data,
    )

    with pytest.raises(
        vlr_upcoming.MatchNotForecastableError
    ):
        vlr_upcoming.parse_upcoming_match(
            None,
            None,
        )