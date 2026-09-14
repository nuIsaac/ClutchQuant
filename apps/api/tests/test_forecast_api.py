from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_db
from app.main import app
from app.models import Base, Match, Team


engine = create_engine(
    "sqlite://",
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture
def database():
    Base.metadata.create_all(bind=engine)

    try:
        yield TestingSessionLocal

    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(database):
    def override_get_db():
        db = database()

        try:
            yield db

        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def scheduled_match(database):
    db = database()

    team1 = Team(
        vlr_id=900001,
        name="Test Team One",
    )

    team2 = Team(
        vlr_id=900002,
        name="Test Team Two",
    )

    db.add_all([
        team1,
        team2,
    ])

    db.flush()

    match = Match(
        vlr_id=900003,
        team1_id=team1.id,
        team2_id=team2.id,
        event_name="Test Event",
        stage="Test Stage",
        status="scheduled",
        scheduled_at=(
            datetime.now(timezone.utc)
            + timedelta(hours=2)
        ),
    )

    db.add(match)
    db.commit()

    match_id = match.id

    db.close()

    return match_id


def test_lists_upcoming_matches(
    client,
    scheduled_match,
):
    response = client.get(
        "/api/v1/matches/upcoming"
    )

    assert response.status_code == 200

    matches = response.json()

    assert len(matches) == 1
    assert matches[0]["id"] == scheduled_match
    assert matches[0]["team1_name"] == "Test Team One"
    assert matches[0]["team2_name"] == "Test Team Two"


def test_forecast_is_created_and_cannot_be_overwritten(
    client,
    scheduled_match,
):
    payload = {
        "match_id": scheduled_match,
        "source_type": "human",
        "source_key": "human:test",
        "team1_win_probability": 0.65,
        "rationale": "Test forecast.",
    }

    created = client.post(
        "/api/v1/forecasts",
        json=payload,
    )

    duplicate = client.post(
        "/api/v1/forecasts",
        json=payload,
    )

    assert created.status_code == 201
    assert duplicate.status_code == 409

    forecast = created.json()

    assert forecast["match_id"] == scheduled_match
    assert forecast["team1_win_probability"] == 0.65


def test_forecast_rejects_invalid_probability(
    client,
    scheduled_match,
):
    response = client.post(
        "/api/v1/forecasts",
        json={
            "match_id": scheduled_match,
            "source_type": "human",
            "source_key": "human:test",
            "team1_win_probability": 1.5,
        },
    )

    assert response.status_code == 422


def test_forecast_rejects_completed_match(
    client,
    database,
    scheduled_match,
):
    db = database()

    match = db.get(
        Match,
        scheduled_match,
    )

    match.status = "completed"

    db.commit()
    db.close()

    response = client.post(
        "/api/v1/forecasts",
        json={
            "match_id": scheduled_match,
            "source_type": "human",
            "source_key": "human:test",
            "team1_win_probability": 0.65,
        },
    )

    assert response.status_code == 409


def test_scores_completed_forecast(
    client,
    database,
    scheduled_match,
):
    created = client.post(
        "/api/v1/forecasts",
        json={
            "match_id": scheduled_match,
            "source_type": "human",
            "source_key": "human:test",
            "team1_win_probability": 0.65,
            "rationale": "Test forecast.",
        },
    )

    assert created.status_code == 201

    db = database()

    match = db.get(
        Match,
        scheduled_match,
    )

    match.status = "completed"
    match.team1_score = 2
    match.team2_score = 1

    db.commit()
    db.close()

    response = client.get(
        "/api/v1/forecasts/scores",
        params={
            "match_id": scheduled_match,
        },
    )

    assert response.status_code == 200

    scores = response.json()

    assert len(scores) == 1

    score = scores[0]

    assert score["team1_outcome"] == 1
    assert score["brier_score"] == pytest.approx(
        0.1225
    )
    assert score["log_loss"] == pytest.approx(
        0.4307829
    )


@pytest.mark.parametrize("source_type,source_key", [
    ("model", "model:elo:v1"),
    ("human", "model:elo:v1"),
    ("market", "market:test"),
    ("human", "human:"),
    ("human", " human:test"),
])
def test_public_submissions_cannot_claim_internal_sources(
    client, scheduled_match, source_type, source_key,
):
    response = client.post("/api/v1/forecasts", json={
        "match_id": scheduled_match,
        "source_type": source_type,
        "source_key": source_key,
        "team1_win_probability": 0.65,
    })
    assert response.status_code == 422
    assert client.get("/api/v1/forecasts").json() == []


def submit_forecast(client, match_id):
    response = client.post("/api/v1/forecasts", json={
        "match_id": match_id,
        "source_type": "human",
        "source_key": "human:test",
        "team1_win_probability": 0.8,
    })
    assert response.status_code == 201
    return response.json()


def test_scoring_follows_forecast_teams_when_result_order_reverses(
    client, database, scheduled_match,
):
    forecast = submit_forecast(client, scheduled_match)
    with database() as db:
        match = db.get(Match, scheduled_match)
        match.team1_id, match.team2_id = match.team2_id, match.team1_id
        match.team1_score, match.team2_score = 0, 2
        match.status = "completed"
        db.commit()

    response = client.get("/api/v1/forecasts/scores")
    assert response.status_code == 200
    score, = response.json()
    assert score["team1_id"] == forecast["team1_id"]
    assert score["team2_id"] == forecast["team2_id"]
    assert score["team1_name"] == "Test Team One"
    assert (score["team1_score"], score["team2_score"]) == (2, 0)
    assert score["team1_outcome"] == 1
    assert score["brier_score"] == pytest.approx(0.04)
    assert score["log_loss"] == pytest.approx(0.223143551)


def test_replacement_opponent_is_unscored_but_forecast_is_preserved(
    client, database, scheduled_match,
):
    forecast = submit_forecast(client, scheduled_match)
    with database() as db:
        replacement = Team(vlr_id=900004, name="Replacement Team")
        db.add(replacement)
        db.flush()
        match = db.get(Match, scheduled_match)
        match.team2_id = replacement.id
        match.team1_score, match.team2_score = 2, 0
        match.status = "completed"
        db.commit()

    assert client.get("/api/v1/forecasts/scores").json() == []
    assert client.get("/api/v1/forecasts").json() == [forecast]


@pytest.mark.parametrize("score1,score2", [(0, 0), (1, 1), (None, 2), (-1, 2)])
def test_ineligible_results_are_preserved_and_unscored(
    client, database, scheduled_match, score1, score2,
):
    forecast = submit_forecast(client, scheduled_match)
    with database() as db:
        match = db.get(Match, scheduled_match)
        match.team1_score, match.team2_score = score1, score2
        match.status = "completed"
        db.commit()

    assert client.get("/api/v1/forecasts/scores").json() == []
    assert client.get("/api/v1/forecasts").json() == [forecast]
    with database() as db:
        match = db.get(Match, scheduled_match)
        assert (match.team1_score, match.team2_score) == (score1, score2)


def test_forecast_rejects_elapsed_deadline(client, database, scheduled_match):
    with database() as db:
        db.get(Match, scheduled_match).scheduled_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        db.commit()
    response = client.post("/api/v1/forecasts", json={
        "match_id": scheduled_match,
        "source_type": "human",
        "source_key": "human:test",
        "team1_win_probability": 0.8,
    })
    assert response.status_code == 409
    assert "deadline" in response.json()["detail"]


def test_schedule_changes_do_not_rewrite_existing_forecast(
    client, database, scheduled_match,
):
    forecast = submit_forecast(client, scheduled_match)
    with database() as db:
        match = db.get(Match, scheduled_match)
        match.scheduled_at += timedelta(days=1)
        db.commit()
    assert client.get("/api/v1/forecasts").json() == [forecast]


def test_upcoming_includes_individual_forecasts(client,scheduled_match):
    forecast = submit_forecast(client,scheduled_match)
    result = client.get("/api/v1/matches/upcoming/forecasts")
    assert result.status_code == 200
    assert result.json()[0]["forecasts"] == [forecast]
    assert client.get("/api/v1/forecasts",params={"source_key":"model:missing"}).json() == []
    assert client.get("/api/v1/forecasts",params={"limit":501}).status_code == 422


def test_production_write_gate(client,scheduled_match,monkeypatch):
    from app import settings
    monkeypatch.setattr(settings,"APP_ENV","production")
    monkeypatch.setattr(settings,"HUMAN_FORECAST_TOKEN",None)
    payload = {"match_id":scheduled_match,"source_type":"human","source_key":"human:operator","team1_win_probability":0.6}
    assert client.post("/api/v1/forecasts",json=payload).status_code == 403
    monkeypatch.setattr(settings,"HUMAN_FORECAST_TOKEN","synthetic-test-token")
    assert client.post("/api/v1/forecasts",json=payload).status_code == 401
    assert client.post("/api/v1/forecasts",json=payload,headers={"Authorization":"Bearer synthetic-test-token"}).status_code == 201
