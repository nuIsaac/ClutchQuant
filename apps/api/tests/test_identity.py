import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ingestion.vlr import get_or_create_team
from app.ingestion.vlr_stats import get_or_create_player
from app.models import Base, Player, Team


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "player_data",
    [
        {},
        {"player_name": "Unresolved"},
        {"vlr_player_id": None, "player_name": "Unresolved"},
        {"vlr_player_id": 0, "player_name": "Unresolved"},
        {"vlr_player_id": -1, "player_name": "Unresolved"},
        {"vlr_player_id": True, "player_name": "Unresolved"},
        {"vlr_player_id": "123", "player_name": "Unresolved"},
        {"vlr_player_id": 123.0, "player_name": "Unresolved"},
        {"vlr_player_id": 123},
        {"vlr_player_id": 123, "player_name": None},
        {"vlr_player_id": 123, "player_name": ""},
        {"vlr_player_id": 123, "player_name": "   "},
        {"vlr_player_id": 123, "player_name": 123},
    ],
)
def test_invalid_player_identity_preserves_existing_records(db, player_data):
    unknown = Player(vlr_id=None, handle="Original unresolved player")
    known = Player(vlr_id=123, handle="Known player")
    db.add_all([unknown, known])
    db.commit()
    expected = [(row.id, row.vlr_id, row.handle) for row in (unknown, known)]

    with pytest.raises(ValueError):
        get_or_create_player(db, player_data)

    assert not db.new
    assert not db.dirty
    db.commit()
    db.expire_all()
    assert [
        (row.id, row.vlr_id, row.handle)
        for row in db.query(Player).order_by(Player.id)
    ] == expected


def test_player_lookup_uses_vlr_identity_and_updates_handle(db):
    original = get_or_create_player(
        db, {"vlr_player_id": 123, "player_name": "Old handle"}
    )
    original_id = original.id
    db.commit()

    renamed = get_or_create_player(
        db, {"vlr_player_id": 123, "player_name": " New handle "}
    )
    db.commit()

    assert renamed.id == original_id
    assert renamed.handle == "New handle"
    assert db.query(Player).count() == 1


def test_known_player_does_not_claim_unknown_or_same_handle_identity(db):
    unknown = Player(vlr_id=None, handle="Shared handle")
    other = Player(vlr_id=124, handle="Shared handle")
    db.add_all([unknown, other])
    db.commit()

    resolved = get_or_create_player(
        db, {"vlr_player_id": 123, "player_name": "Shared handle"}
    )
    db.commit()

    assert len({unknown.id, other.id, resolved.id}) == 3
    assert unknown.vlr_id is None
    assert other.vlr_id == 124
    assert resolved.vlr_id == 123


def test_distinct_vlr_teams_can_share_names_and_rename_independently(db):
    first = get_or_create_team(db, {"vlr_id": 123, "name": "Shared name"})
    second = get_or_create_team(db, {"vlr_id": 124, "name": "Shared name"})
    db.commit()

    assert first.id != second.id
    assert first.name == second.name == "Shared name"

    renamed = get_or_create_team(db, {"vlr_id": 123, "name": "New name"})
    db.commit()

    assert renamed.id == first.id
    assert first.name == "New name"
    assert second.name == "Shared name"
    assert db.query(Team).count() == 2


def test_team_vlr_identity_remains_unique(db):
    db.add(Team(vlr_id=123, name="First name"))
    db.commit()
    db.add(Team(vlr_id=123, name="Different name"))

    with pytest.raises(IntegrityError):
        db.commit()
