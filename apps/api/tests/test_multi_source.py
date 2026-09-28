from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models import Base, Team, Match, MatchSource, MatchObservation, TeamAlias, SourceIssue
from app.ingestion.resolution import resolve_team, save_source_match, normalize, UnresolvedTeam
from app.ingestion.multi_source import sync_sources
from app.data_sources.thespike import ThespikeSource


@pytest.fixture
def db(tmp_path, monkeypatch):
    import app.artifacts as artifacts
    monkeypatch.setattr(artifacts, "ARTIFACT_ROOT", tmp_path / "artifacts")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def record(source="vlr", external="100", **updates):
    value = dict(source=source, external_id=external,
        team1={"external_id": "1" if source == "vlr" else "11", "name": "PCIFIC Esports"},
        team2={"external_id": "2" if source == "vlr" else "22", "name": "Fear Never Ends"},
        scheduled_at=datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1),
        event_name="Synthetic event", stage="Decider", status="scheduled", team1_score=None, team2_score=None,
        source_url=f"https://www.{source}.gg/{external}")
    return value | updates


@pytest.mark.parametrize("name", ["PCIFIC Esports", "pcific esports", "  PCIFIC   ESPORTS  ", "ＰＣＩＦＩＣ Esports", "PCIFIC.Esports"])
def test_team_normalization(db, name):
    original = resolve_team(db, "vlr", {"external_id": "1", "name": "PCIFIC Esports"})
    other = resolve_team(db, "thespike", {"external_id": "11", "name": name})
    assert other.id == original.id


def test_alias_unknown_and_ambiguous(db):
    original = resolve_team(db, "vlr", {"external_id": "1", "name": "PCIFIC Esports"})
    db.add(TeamAlias(team_id=original.id, source="thespike", alias="PCIFIC", normalized_alias=normalize("PCIFIC")))
    db.flush()
    assert resolve_team(db, "thespike", {"external_id": "11", "name": "PCIFIC"}).id == original.id
    unknown = resolve_team(db, "thespike", {"external_id": "12", "name": "New team"})
    assert unknown.id != original.id
    db.add_all([Team(name="Shared", vlr_id=3), Team(name="Shared", vlr_id=4)])
    db.flush()
    with pytest.raises(UnresolvedTeam):
        resolve_team(db, "thespike", {"external_id": "13", "name": "Shared"})
    assert db.scalar(select(SourceIssue)).kind == "UNRESOLVED_TEAM"


def test_same_source_distinct_identity_not_merged(db):
    a = resolve_team(db, "vlr", {"external_id": "1", "name": "Same name"})
    b = resolve_team(db, "vlr", {"external_id": "2", "name": "Same name"})
    assert a.id != b.id


@pytest.mark.parametrize("first", ["vlr", "thespike"])
def test_cross_source_order_time_tolerance_and_idempotency(db, first):
    a = record(first)
    match = save_source_match(db, a)
    second = "thespike" if first == "vlr" else "vlr"
    b = record(second, scheduled_at=a["scheduled_at"] + timedelta(minutes=15))
    b["team1"], b["team2"] = b["team2"], b["team1"]
    assert save_source_match(db, b).id == match.id
    assert save_source_match(db, b).id == match.id
    assert db.query(Match).count() == 1
    assert db.query(MatchSource).count() == 2
    assert db.query(SourceIssue).filter_by(kind="SOURCE_CONFLICT").count() == 1


@pytest.mark.parametrize("change", ["date", "stage", "event", "same_source"])
def test_rematches_stay_separate(db, change):
    a = record()
    save_source_match(db, a)
    b = record("thespike", scheduled_at=a["scheduled_at"])
    if change == "date": b["scheduled_at"] += timedelta(days=2)
    if change == "stage": b["stage"] = "Final"
    if change == "event": b["event_name"] = "Another tournament"
    if change == "same_source": b = record(external="101", scheduled_at=a["scheduled_at"])
    save_source_match(db, b)
    assert db.query(Match).count() == 2


def test_conflicting_secondary_evidence_not_used_for_training(db):
    from app.artifacts import write_bytes
    a = record()
    match = save_source_match(db, a)
    b = record("thespike", scheduled_at=a["scheduled_at"] + timedelta(minutes=15),
               evidence={"received_at": datetime.now(timezone.utc).isoformat(),
                         "raw_sha256": write_bytes("raw", b"synthetic"), "source_url": "https://www.thespike.gg/test"})
    save_source_match(db, b)
    assert match.scheduled_at == a["scheduled_at"]
    assert db.query(MatchObservation).count() == 0
    assert db.query(SourceIssue).count() == 1
    assert db.query(MatchSource).filter_by(source="thespike").one().details["scheduled_at"] == b["scheduled_at"].isoformat()


@pytest.mark.parametrize("vlr_fails,spike_fails", [(False,False),(False,True),(True,False),(True,True)])
def test_independent_source_failures(db, vlr_fails, spike_fails):
    at = record()["scheduled_at"]
    def source(name, fail):
        def discover(pages):
            if fail: raise RuntimeError("Synthetic outage")
            yield record(name, scheduled_at=at)
        return SimpleNamespace(name=name, discover_upcoming_matches=discover)
    result = sync_sources([source("vlr", vlr_fails), source("thespike", spike_fails)], session_factory=lambda: Session(db.bind))
    assert result["failed"] == int(vlr_fails) + int(spike_fails)
    assert result["saved"] == 2 - int(vlr_fails) - int(spike_fails)
    assert result["coverage"]["upcoming"]["canonical_total"] == int(not (vlr_fails and spike_fails))


def test_authorized_export_only_and_actual_receipt(db, tmp_path):
    item = record("thespike")
    item["scheduled_at"] = item["scheduled_at"].isoformat()
    item["received_at"] = "2020-01-01T00:00:00Z"  # Never trust caller-supplied historical availability.
    path = tmp_path / "export.json"
    path.write_text(json.dumps([item]))
    before = datetime.now(timezone.utc)
    data = list(ThespikeSource(path).discover_upcoming_matches())[0]
    assert datetime.fromisoformat(data["evidence"]["received_at"]) >= before
    match = save_source_match(db, data)
    assert match.vlr_id is None
    assert db.query(MatchObservation).count() == 1
    item["team1_score"] = 2
    path.write_text(json.dumps([item]))
    with pytest.raises(ValueError, match="upcoming"):
        list(ThespikeSource(path).discover_upcoming_matches())


def test_ambiguous_match_is_preserved_for_review(db):
    at = record()["scheduled_at"]
    save_source_match(db, record(external="100", scheduled_at=at))
    save_source_match(db, record(external="101", scheduled_at=at + timedelta(minutes=20)))
    save_source_match(db, record("thespike", scheduled_at=at + timedelta(minutes=10)))
    assert db.query(Match).count() == 3
    assert db.query(SourceIssue).filter_by(kind="AMBIGUOUS_MATCH").count() == 1


def test_suffix_similarity_requires_review_instead_of_duplicate(db):
    resolve_team(db, "vlr", {"external_id":"1", "name":"PCIFIC Esports"})
    with pytest.raises(UnresolvedTeam, match="Alias review"):
        resolve_team(db, "thespike", {"external_id":"11", "name":"PCIFIC"})
    assert db.query(Team).count() == 1


def test_format_mismatch_not_merged(db):
    a = record(best_of=3)
    save_source_match(db, a)
    save_source_match(db, record("thespike", best_of=5, scheduled_at=a["scheduled_at"]))
    assert db.query(Match).count() == 2


def test_vlr_map_scores_keep_canonical_orientation(db):
    from app.ingestion.vlr_stats import save_maps
    from app.models import MatchMap
    a = record("thespike")
    match = save_source_match(db, a)
    b = record(scheduled_at=a["scheduled_at"])
    b["team1"], b["team2"] = b["team2"], b["team1"]
    assert save_source_match(db, b).id == match.id
    save_maps(db, match, [{"vlr_game_id":1001, "map_number":1, "map_name":"Ascent", "team1_score":13,
                           "team2_score":5, "duration_seconds":2000, "players":[]}])
    db.flush()
    result = db.scalar(select(MatchMap))
    assert (result.team1_score, result.team2_score) == (5, 13)


def test_stale_export_does_not_refresh_schedule_evidence(db, tmp_path):
    import os
    path = tmp_path / "stale.json"
    path.write_text("[]")
    os.utime(path, (1,1))
    with pytest.raises(ValueError, match="15 minutes"):
        list(ThespikeSource(path).discover_upcoming_matches())


def test_unknown_legacy_identity_not_claimed_by_name(db):
    unknown = Team(name="Unknown legacy", vlr_id=None)
    db.add(unknown)
    db.flush()
    with pytest.raises(UnresolvedTeam, match="explicit identity review"):
        resolve_team(db, "vlr", {"external_id":"123", "name":unknown.name})
    assert unknown.vlr_id is None
