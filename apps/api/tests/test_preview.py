from datetime import datetime, timezone
from app.research.preview import build_state, encode
from app.research.elo import expected_score

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_research_elo_uses_results_without_inventing_availability():
    rows = [[1, 10, 20, 2, 0, "2020-01-01T00:00:00+00:00"]]
    ratings, used = build_state(rows, NOW)
    assert ratings == {10: 1516, 20: 1484}
    assert expected_score(ratings[10], ratings[20]) > .5
    assert used == rows and b"observed" not in encode(used)


def test_ties_future_same_team_and_retractions_are_excluded():
    rows = [None, [1, 10, 20, 1, 1, "2020-01-01T00:00:00+00:00"],
            [2, 10, 20, 2, 0, "2030-01-01T00:00:00+00:00"],
            [3, 10, 10, 2, 0, "2020-01-01T00:00:00+00:00"]]
    assert build_state(rows, NOW) == ({}, [])


def test_chronology_is_deterministic():
    rows = [[2, 10, 20, 0, 2, "2021-01-01T00:00:00+00:00"],
            [1, 10, 20, 2, 0, "2020-01-01T00:00:00+00:00"]]
    assert build_state(rows, NOW) == build_state(list(reversed(rows)), NOW)


def test_preview_maps_stable_vlr_ids_and_cloud_retractions(monkeypatch):
    from app.research import preview
    from types import SimpleNamespace
    monkeypatch.setattr(preview, "load_history", lambda: {
        "rows": [[1, 10, 20, 2, 0, "2020-01-01T00:00:00+00:00"]],
        "sha256": "a" * 64, "exported_at": NOW.isoformat()})
    monkeypatch.setattr(preview, "current_rows", lambda _: {})
    class DB:
        def execute(self, statement):
            assert statement.is_select
            return SimpleNamespace(all=lambda: [(100, 10), (200, 30)])
    match = SimpleNamespace(id=8, team1_id=100, team2_id=200)
    result = preview.previews(DB(), [match])[8]
    assert result["team1_rating"] == 1516 and result["team2_rating"] == 1500
    assert result["team2_unseen"] and result["team2_history_count"] == 0
    assert result["team1_win_probability"] > .5
    assert result["used_for_prospective_scoring"] is False
    assert result["availability"] == "UNKNOWN"
    monkeypatch.setattr(preview, "current_rows", lambda _: {1: None})
    assert preview.previews(DB(), [match]) == {}
