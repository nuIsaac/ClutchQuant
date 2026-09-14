from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.match_eligibility import eligible_matches_query, match_exclusion_reason
from app.models import Base, Forecast, Match, Team
from app.research import backtest_elo, generate_elo_forecasts
from app.research.audit_matches import audit_matches
from app.research.elo import expected_score


PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([Team(id=1, name="One"), Team(id=2, name="Two")])
        db.commit()
    yield factory
    engine.dispose()


def series(**overrides):
    fields = dict(
        team1_id=1, team2_id=2, team1_score=2, team2_score=0,
        scheduled_at=PAST, status="completed",
    )
    fields.update(overrides)
    return Match(**fields)


@pytest.mark.parametrize("overrides,reason", [
    ({}, None),
    ({"status": "scheduled"}, "not_completed"),
    ({"status": None}, "not_completed"),
    ({"team1_score": None}, "missing_score"),
    ({"team2_score": None}, "missing_score"),
    ({"team1_score": -1}, "negative_score"),
    ({"team1_score": 0, "team2_score": 0}, "tied_score"),
    ({"team1_score": 1, "team2_score": 1}, "tied_score"),
    ({"team2_id": 1}, "same_team"),
    ({"scheduled_at": None}, "missing_start_time"),
])
def test_eligibility_reports_reasons_without_altering_records(sessions, overrides, reason):
    with sessions() as db:
        match = series(**overrides)
        db.add(match)
        db.commit()
        original = (match.status, match.team1_score, match.team2_score, match.scheduled_at)
        assert db.scalar(select(match_exclusion_reason()).select_from(Match)) == reason
        assert db.scalars(eligible_matches_query()).all() == ([match] if reason is None else [])
        report = audit_matches(db)
        assert report["counts"] == {reason or "eligible": 1}
        assert report["excluded_matches"] == ([] if reason is None else [{
            "match_id": match.id, "vlr_id": None, "reason": reason,
        }])
        db.expire_all()
        assert (match.status, match.team1_score, match.team2_score, match.scheduled_at) == original


def test_backtest_predicts_before_update_and_uses_deterministic_history(sessions, monkeypatch):
    with sessions() as db:
        db.add_all([
            series(id=30, scheduled_at=PAST + timedelta(days=1)),
            series(id=20, team1_score=0, team2_score=2),
            series(id=10),
            series(id=1, status="scheduled"),
            series(id=2, team1_score=0, team2_score=0),
        ])
        db.commit()

    seen = []
    original_predict = backtest_elo.predict_match

    def record_prediction(ratings, team1_id, team2_id):
        probability = original_predict(ratings, team1_id, team2_id)
        seen.append(probability)
        return probability

    monkeypatch.setattr(backtest_elo, "SessionLocal", sessions)
    monkeypatch.setattr(backtest_elo, "predict_match", record_prediction)
    backtest_elo.run_elo_backtest()
    assert len(seen) == 3
    assert seen[0] == 0.5
    assert seen[1] == pytest.approx(expected_score(1516, 1484))
    # ID 20 loses after ID 10 wins at the same timestamp; the next day's
    # prediction must include both results, not the scheduled/tied rows.
    assert seen[2] < 0.5


def test_generator_uses_eligible_past_results_and_preserves_existing_forecasts(sessions, monkeypatch):
    now = datetime.now(timezone.utc)
    with sessions() as db:
        db.add_all([
            series(id=1),
            series(id=2, team1_score=0, team2_score=0),
            series(id=3, team1_score=0, team2_score=2, status="scheduled"),
            series(id=4, team1_score=-1),
            series(id=5, scheduled_at=None),
            series(id=6, scheduled_at=now + timedelta(days=2)),
            series(id=7, team2_id=1),
            series(id=8, status="scheduled", team1_score=None, team2_score=None,
                   scheduled_at=now + timedelta(hours=1)),
        ])
        db.commit()
    monkeypatch.setattr(generate_elo_forecasts, "SessionLocal", sessions)
    generate_elo_forecasts.generate_elo_forecasts()
    with sessions() as db:
        forecast, = db.scalars(select(Forecast)).all()
        assert forecast.match_id == 8
        assert forecast.source_key == "model:elo:v1"
        assert forecast.team1_win_probability == pytest.approx(expected_score(1516, 1484))
        assert forecast.created_at < forecast.lock_time
        original = (forecast.id, forecast.team1_win_probability, forecast.created_at)
        # New evidence must not silently overwrite the original prediction.
        db.add(series(id=9, team1_score=0, team2_score=2,
                      scheduled_at=PAST + timedelta(days=1)))
        db.commit()
    generate_elo_forecasts.generate_elo_forecasts()
    with sessions() as db:
        forecast, = db.scalars(select(Forecast)).all()
        assert (forecast.id, forecast.team1_win_probability, forecast.created_at) == original


def test_generator_skips_deadline_crossed_during_run(sessions, monkeypatch):
    now = datetime.now(timezone.utc)
    with sessions() as db:
        db.add(series(status="scheduled", team1_score=None, team2_score=None,
                      scheduled_at=now + timedelta(minutes=1)))
        db.commit()
    times = iter([now, now, now + timedelta(minutes=2)])

    class AdvancingClock:
        @staticmethod
        def now(tz):
            return next(times)

    monkeypatch.setattr(generate_elo_forecasts, "SessionLocal", sessions)
    monkeypatch.setattr(generate_elo_forecasts, "datetime", AdvancingClock)
    generate_elo_forecasts.generate_elo_forecasts()
    with sessions() as db:
        assert db.scalars(select(Forecast)).all() == []


def test_generator_checks_deadline_after_slow_existing_forecast_lookup(sessions, monkeypatch):
    now = datetime.now(timezone.utc)
    clock_time = now
    with sessions() as db:
        db.add(series(status="scheduled", team1_score=None, team2_score=None,
                      scheduled_at=now + timedelta(minutes=1)))
        db.commit()

    class Clock:
        @staticmethod
        def now(tz):
            return clock_time

    original_scalar = Session.scalar

    def slow_lookup(self, *args, **kwargs):
        nonlocal clock_time
        result = original_scalar(self, *args, **kwargs)
        clock_time = now + timedelta(minutes=2)
        return result

    monkeypatch.setattr(generate_elo_forecasts, "SessionLocal", sessions)
    monkeypatch.setattr(generate_elo_forecasts, "datetime", Clock)
    monkeypatch.setattr(Session, "scalar", slow_lookup)
    generate_elo_forecasts.generate_elo_forecasts()
    with sessions() as db:
        assert db.scalars(select(Forecast)).all() == []
