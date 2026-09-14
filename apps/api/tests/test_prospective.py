from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.research.generate_models import prepare, schedule_evidence


def test_cold_start_is_explicit_and_frozen_v1_prior():
    data = {"as_of":"2026-09-14T12:00:00Z","rows":[],"result_events":[]}
    assert prepare(data) is None
    states,_,classifiers,count = prepare(data,allow_cold_start=True)
    assert count == 0
    assert states["elo_v1"].predict(1,2,datetime.now(timezone.utc)) == .5
    assert all(value is None for value in classifiers.values())


@pytest.mark.parametrize("change",["stale","future","changed_team","completed","changed_schedule"])
def test_freeze_rejects_unsupported_schedule(change):
    now = datetime.now(timezone.utc)
    match = SimpleNamespace(id=1,team1_id=1,team2_id=2,scheduled_at=now+timedelta(hours=1))
    event = {"id":1,"observation_id":1,"team1_id":1,"team2_id":2,"status":"scheduled",
             "scheduled_at":match.scheduled_at.isoformat(),"result_observed_at":now.isoformat()}
    assert schedule_evidence({"result_events":[event]},match,now,900) == event
    if change == "stale": event["result_observed_at"] = (now-timedelta(hours=1)).isoformat()
    if change == "future": event["result_observed_at"] = (now+timedelta(seconds=1)).isoformat()
    if change == "changed_team": event["team2_id"] = 3
    if change == "completed": event["status"] = "completed"
    if change == "changed_schedule": event["scheduled_at"] = (now+timedelta(hours=2)).isoformat()
    assert schedule_evidence({"result_events":[event]},match,now,900) is None


def test_pipeline_stops_after_collection_failure(monkeypatch):
    from app import pipeline
    class Guard:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def scalar(self,*args): return True
        def execute(self,*args): pass
    class DB(Guard):
        def add(self,value): pass
        def commit(self): pass
    monkeypatch.setattr(pipeline,"engine",SimpleNamespace(connect=lambda:Guard()))
    monkeypatch.setattr(pipeline,"SessionLocal",DB)
    monkeypatch.setattr(pipeline,"write_json",lambda *args:"0"*64)
    monkeypatch.setattr(pipeline,"sync_recent_results",lambda pages:{"failed":1})
    monkeypatch.setattr(pipeline,"generate",lambda *args,**kwargs:pytest.fail("Must not forecast after failure"))
    assert pipeline.run_cycle()["status"] == "FAILED"


def test_pipeline_skips_overlapping_run(monkeypatch):
    from app import pipeline
    class Guard:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def scalar(self,*args): return False
    monkeypatch.setattr(pipeline,"engine",SimpleNamespace(connect=lambda:Guard()))
    assert pipeline.run_cycle() == {"status":"SKIPPED_OVERLAP"}


@pytest.mark.parametrize("case",["reversed","changed","early","tied"])
def test_prospective_outcome_rules(monkeypatch,case):
    from app.research import prospective
    monkeypatch.setattr(prospective,"verify_forecast",lambda *_:None)
    now = datetime.now(timezone.utc)
    forecast = SimpleNamespace(match_id=1,team1_id=1,team2_id=2,created_at=now,
                               team1_win_probability=.75)
    event = {"id":1,"observation_id":2,"team1_id":1,"team2_id":2,
             "team1_score":2,"team2_score":0,"status":"completed","exclusion_reason":None,
             "scheduled_at":(now+timedelta(hours=1)).isoformat(),
             "result_observed_at":(now+timedelta(hours=2)).isoformat(),"raw_sha256":"0"*64}
    expected = "VERIFIED_PROSPECTIVE"
    if case == "reversed":
        event.update(team1_id=2,team2_id=1,team1_score=0,team2_score=2)
    if case == "changed":
        event["team2_id"] = 3
        expected = "PARTICIPANTS_CHANGED"
    if case == "early":
        event["scheduled_at"] = (now-timedelta(minutes=1)).isoformat()
        expected = "RESULT_OR_START_BEFORE_FORECAST"
    if case == "tied":
        event.update(team2_score=2,exclusion_reason="tied_score")
        expected = "INELIGIBLE_RESULT"
    score = prospective.score_frozen(forecast,None,[event],now+timedelta(hours=3))
    assert score["status"] == expected
    if case == "reversed":
        assert score["outcome"] == 1 and score["brier"] == .0625
