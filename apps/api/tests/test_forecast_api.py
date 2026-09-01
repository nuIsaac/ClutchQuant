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