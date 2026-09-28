"""Opt-in tests against PostgreSQL, including the real Alembic upgrade chain.

Set TEST_DATABASE_URL explicitly, then run from apps/api:
    python -m pytest tests/test_postgres_contract.py -q

Each test owns a newly generated schema. The connection's local search path
contains only that schema; no application/default database URL is used. Test
transactions are rolled back and only the schema created by the fixture is
dropped. The configured PostgreSQL role must be allowed to create schemas.
"""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, insert, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models import Forecast, Match, MatchObservation, ModelRun, Player, Team


API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_HEAD = "eaf7597a5438"
SCHEMA_PATTERN = re.compile(r"clutchquant_test_[0-9a-f]{32}")
CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
LOCK_TIME = CREATED_AT + timedelta(hours=2)


def migration_config(connection):
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def postgres_connection():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to opt into PostgreSQL integration tests")

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must explicitly identify PostgreSQL")
    if not url.database:
        pytest.fail("TEST_DATABASE_URL must explicitly name a database")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")

    schema = f"clutchquant_test_{uuid4().hex}"
    if not SCHEMA_PATTERN.fullmatch(schema):
        raise RuntimeError("Refusing an invalid test schema name")

    engine = create_engine(url, connect_args={"connect_timeout": 5})
    schema_created = False
    try:
        with engine.begin() as setup:
            # Do not use IF NOT EXISTS: cleanup is authorized only for a schema
            # that this fixture actually created, never a pre-existing schema.
            setup.execute(CreateSchema(schema))
        schema_created = True

        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                quoted_schema = connection.dialect.identifier_preparer.quote(schema)
                connection.exec_driver_sql(
                    f"SET LOCAL search_path TO {quoted_schema}"
                )
                connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
                assert connection.scalar(text("SELECT current_schema()")) == schema
                assert connection.scalar(
                    text("SELECT current_schemas(false)")
                ) == [schema]
                yield connection
            finally:
                if transaction.is_active:
                    transaction.rollback()
    finally:
        try:
            if schema_created:
                if not SCHEMA_PATTERN.fullmatch(schema):
                    raise RuntimeError("Refusing to drop an unowned test schema")
                with engine.begin() as cleanup:
                    cleanup.execute(DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


@pytest.fixture
def migrated_connection(postgres_connection):
    command.upgrade(migration_config(postgres_connection), "head")
    return postgres_connection


@pytest.fixture
def forecast_values(migrated_connection):
    connection = migrated_connection
    team1_id = connection.scalar(
        insert(Team).values(name="Contract Team One", vlr_id=1001).returning(Team.id)
    )
    team2_id = connection.scalar(
        insert(Team).values(name="Contract Team Two", vlr_id=1002).returning(Team.id)
    )
    match_id = connection.scalar(
        insert(Match)
        .values(
            vlr_id=2001,
            team1_id=team1_id,
            team2_id=team2_id,
            status="scheduled",
            scheduled_at=LOCK_TIME,
        )
        .returning(Match.id)
    )
    return {
        "match_id": match_id,
        "team1_id": team1_id,
        "team2_id": team2_id,
        "source_type": "model",
        "source_key": "model:elo:v1",
        "team1_win_probability": 0.65,
        "created_at": CREATED_AT,
        "lock_time": LOCK_TIME,
    }


def test_upgrade_preserves_existing_data_and_uses_vlr_team_identity(
    postgres_connection,
):
    connection = postgres_connection
    config = migration_config(connection)
    command.upgrade(config, PREVIOUS_HEAD)

    connection.execute(insert(Team), [
        {"id": 1, "vlr_id": 1001, "name": "Same Name"},
        {"id": 2, "vlr_id": 1002, "name": "Other Team"},
    ])
    connection.execute(
        insert(Player).values(id=1, vlr_id=None, handle="Unknown Identity")
    )
    connection.execute(insert(Match).values(
        id=1,
        vlr_id=2001,
        team1_id=1,
        team2_id=2,
        status="completed",
        scheduled_at=LOCK_TIME,
        team1_score=0,
        team2_score=0,
    ))
    connection.execute(insert(Forecast).values(
        id=1,
        match_id=1,
        team1_id=1,
        team2_id=2,
        source_type="model",
        source_key="model:elo:v1",
        team1_win_probability=0.65,
        created_at=CREATED_AT,
        lock_time=LOCK_TIME,
    ))

    command.upgrade(config, "head")

    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
        ScriptDirectory.from_config(config).get_current_head()
    )
    assert connection.execute(
        text("SELECT vlr_id, name FROM teams WHERE id = 1")
    ).one() == (1001, "Same Name")
    assert connection.execute(
        text("SELECT vlr_id, handle FROM players WHERE id = 1")
    ).one() == (None, "Unknown Identity")
    assert connection.execute(
        text("SELECT team1_score, team2_score FROM matches WHERE id = 1")
    ).one() == (0, 0)
    assert connection.scalar(
        text("SELECT team1_win_probability FROM forecasts WHERE id = 1")
    ) == pytest.approx(0.65)

    # Names may collide, while an external VLR ID still identifies one team.
    connection.execute(
        insert(Team).values(id=3, vlr_id=1003, name="Same Name")
    )
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            connection.execute(
                insert(Team).values(id=4, vlr_id=1001, name="Different Name")
            )
    assert error.value.orig.diag.constraint_name == "uq_teams_vlr_id"


def test_team_name_downgrade_restores_uniqueness_without_changing_rows(
    migrated_connection,
):
    connection = migrated_connection
    connection.execute(insert(Team), [
        {"id": 1, "vlr_id": 1001, "name": "First Team"},
        {"id": 2, "vlr_id": 1002, "name": "Second Team"},
    ])
    original_rows = connection.execute(
        text("SELECT id, vlr_id, name FROM teams ORDER BY id")
    ).all()

    command.downgrade(migration_config(connection), PREVIOUS_HEAD)

    assert connection.scalar(
        text("SELECT version_num FROM alembic_version")
    ) == PREVIOUS_HEAD
    assert connection.execute(
        text("SELECT id, vlr_id, name FROM teams ORDER BY id")
    ).all() == original_rows
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            connection.execute(
                insert(Team).values(id=3, vlr_id=1003, name="First Team")
            )
    assert error.value.orig.diag.constraint_name == "teams_name_key"


def test_team_name_downgrade_with_duplicates_fails_and_preserves_data(
    migrated_connection,
):
    connection = migrated_connection
    config = migration_config(connection)
    original_revision = connection.scalar(
        text("SELECT version_num FROM alembic_version")
    )
    connection.execute(insert(Team), [
        {"id": 1, "vlr_id": 1001, "name": "Shared Name"},
        {"id": 2, "vlr_id": 1002, "name": "Shared Name"},
    ])
    original_rows = connection.execute(
        text("SELECT id, vlr_id, name FROM teams ORDER BY id")
    ).all()

    # The SAVEPOINT models a failed transactional downgrade while keeping
    # the connection available to verify the existing data and revision.
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            command.downgrade(config, PREVIOUS_HEAD)

    assert error.value.orig.diag.constraint_name == "teams_name_key"
    assert connection.scalar(
        text("SELECT version_num FROM alembic_version")
    ) == original_revision
    assert connection.execute(
        text("SELECT id, vlr_id, name FROM teams ORDER BY id")
    ).all() == original_rows
    # The failed downgrade must not leave a newly installed name constraint.
    connection.execute(
        insert(Team).values(id=3, vlr_id=1003, name="Shared Name")
    )


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        ({"source_type": "unrecognized"}, "ck_forecasts_source_type"),
        ({"team1_win_probability": -0.01}, "ck_forecasts_probability"),
        ({"team1_win_probability": 1.01}, "ck_forecasts_probability"),
        ({"team1_win_probability": float("nan")}, "ck_forecasts_probability"),
        ({"created_at": LOCK_TIME}, "ck_forecasts_before_lock"),
        (
            {"created_at": LOCK_TIME + timedelta(seconds=1)},
            "ck_forecasts_before_lock",
        ),
    ],
)
def test_forecast_checks_apply_to_direct_database_writes(
    migrated_connection, forecast_values, changes, constraint,
):
    with pytest.raises(IntegrityError) as error:
        with migrated_connection.begin_nested():
            migrated_connection.execute(
                insert(Forecast).values(forecast_values | changes)
            )
    assert error.value.orig.diag.constraint_name == constraint


def test_forecast_teams_must_differ(migrated_connection, forecast_values):
    values = forecast_values | {"team2_id": forecast_values["team1_id"]}
    with pytest.raises(IntegrityError) as error:
        with migrated_connection.begin_nested():
            migrated_connection.execute(insert(Forecast).values(values))
    assert error.value.orig.diag.constraint_name == "ck_forecasts_different_teams"


def test_forecast_match_and_source_are_unique(migrated_connection, forecast_values):
    migrated_connection.execute(insert(Forecast).values(forecast_values))
    with pytest.raises(IntegrityError) as error:
        with migrated_connection.begin_nested():
            migrated_connection.execute(insert(Forecast).values(forecast_values))
    assert error.value.orig.diag.constraint_name == "uq_forecasts_match_source"

    migrated_connection.execute(insert(Forecast).values(
        forecast_values | {"source_key": "model:elo:v2"}
    ))
    assert migrated_connection.scalar(text("SELECT count(*) FROM forecasts")) == 2


@pytest.mark.parametrize("field", ["match_id", "team1_id", "team2_id"])
def test_forecast_foreign_keys_are_enforced(
    migrated_connection, forecast_values, field,
):
    with pytest.raises(IntegrityError) as error:
        with migrated_connection.begin_nested():
            migrated_connection.execute(insert(Forecast).values(
                forecast_values | {field: 999999}
            ))
    assert error.value.orig.diag.constraint_name == f"forecasts_{field}_fkey"


@pytest.mark.parametrize("probability", [0.0, 1.0])
def test_forecast_probability_boundaries_are_valid(
    migrated_connection, forecast_values, probability,
):
    forecast_id = migrated_connection.scalar(
        insert(Forecast)
        .values(forecast_values | {"team1_win_probability": probability})
        .returning(Forecast.id)
    )
    stored = migrated_connection.execute(
        text("SELECT team1_win_probability, created_at, lock_time "
             "FROM forecasts WHERE id = :id"),
        {"id": forecast_id},
    ).one()
    assert stored == (probability, CREATED_AT, LOCK_TIME)


def test_history_is_append_only_and_legacy_availability_stays_unknown(
    migrated_connection, forecast_values,
):
    from sqlalchemy.exc import DBAPIError
    migrated_connection.execute(insert(Forecast).values(forecast_values))
    assert migrated_connection.scalar(text("SELECT count(*) FROM match_observations")) == 0
    assert migrated_connection.scalar(text("SELECT model_run_id FROM forecasts")) is None
    for statement in ("UPDATE forecasts SET team1_win_probability=0.9", "DELETE FROM forecasts"):
        with pytest.raises(DBAPIError,match="append-only"):
            with migrated_connection.begin_nested():
                migrated_connection.execute(text(statement))
    assert migrated_connection.scalar(text("SELECT team1_win_probability FROM forecasts")) == 0.65


def test_snapshot_uses_observations_not_export_time(migrated_connection,forecast_values,tmp_path,monkeypatch):
    from sqlalchemy.orm import Session
    import app.artifacts as artifacts
    from app.artifacts import write_bytes
    from app.research.dataset import export_dataset
    monkeypatch.setattr(artifacts,"ARTIFACT_ROOT",tmp_path)
    raw = write_bytes("raw",b"Synthetic source fixture for provenance tests only")
    mid = forecast_values["match_id"]
    migrated_connection.execute(text("UPDATE matches SET status='completed', team1_score=2, team2_score=0 WHERE id=:id"),{"id":mid})
    with Session(bind=migrated_connection) as db:
        _,unknown = export_dataset(db,LOCK_TIME+timedelta(days=1))
        assert unknown["rows"][0]["result_observed_at"] is None
        base = {"team1_id":forecast_values["team1_id"],"team2_id":forecast_values["team2_id"],"scheduled_at":LOCK_TIME.isoformat()}
        db.add_all([
            MatchObservation(match_id=mid,received_at=CREATED_AT,ingested_at=CREATED_AT+timedelta(seconds=1),
                             raw_sha256=raw,source_url="https://example.invalid/fixture",payload=base|{"status":"scheduled"}),
            MatchObservation(match_id=mid,received_at=LOCK_TIME+timedelta(hours=1),ingested_at=LOCK_TIME+timedelta(hours=2),
                             raw_sha256=raw,source_url="https://example.invalid/fixture",payload=base|{"status":"completed","team1_score":2,"team2_score":0}),
        ])
        db.flush()
        key,known = export_dataset(db,LOCK_TIME+timedelta(days=1))
        assert known["rows"][0]["result_observed_at"] == (LOCK_TIME+timedelta(hours=2)).isoformat()
        assert export_dataset(db,LOCK_TIME+timedelta(days=1))[0] == key
        _,earlier = export_dataset(db,LOCK_TIME+timedelta(minutes=30))
        assert earlier["rows"][0]["result_observed_at"] is None


def test_generation_persists_versioned_runs_and_never_overwrites(migrated_connection,forecast_values,tmp_path,monkeypatch):
    from sqlalchemy.orm import Session
    import app.artifacts as artifacts
    from app.artifacts import write_json
    from app.research import generate_models
    monkeypatch.setattr(artifacts,"ARTIFACT_ROOT",tmp_path)
    now = datetime.now(timezone.utc)
    scheduled = now+timedelta(hours=2)
    migrated_connection.execute(text("UPDATE matches SET scheduled_at=:scheduled"),{"scheduled":scheduled})
    history = {
        "as_of":now.isoformat(),"rows":[{
            "id":999,"team1_id":forecast_values["team1_id"],"team2_id":forecast_values["team2_id"],
            "team1_score":2,"team2_score":0,"exclusion_reason":None,"event_name":"Synthetic fixture",
            "scheduled_at":(now-timedelta(days=2)).isoformat(),
            "schedule_observed_at":(now-timedelta(days=3)).isoformat(),
            "result_observed_at":(now-timedelta(days=1)).isoformat(),
        }],
    }
    key = write_json("datasets",history)
    history["result_events"] = history["rows"]
    key = write_json("datasets",history)
    monkeypatch.setattr(generate_models,"snapshot_current",lambda:(key,history))
    monkeypatch.setattr(generate_models,"SessionLocal",lambda:Session(bind=migrated_connection,join_transaction_mode="create_savepoint"))
    first = generate_models.generate(experimental=True)
    assert first["created"] == 4  # Elo variants only; ML has insufficient labeled examples.
    existing = migrated_connection.execute(text("SELECT id,source_key,team1_win_probability,model_run_id FROM forecasts ORDER BY id")).all()
    assert all(row.model_run_id for row in existing)
    assert migrated_connection.scalar(text("SELECT count(*) FROM model_runs")) == 4
    assert generate_models.generate(experimental=True)["created"] == 0
    assert migrated_connection.execute(text("SELECT id,source_key,team1_win_probability,model_run_id FROM forecasts ORDER BY id")).all() == existing
    assert not any("ensemble" in row.source_key for row in existing)


def test_prospective_freeze_score_and_retraction(migrated_connection,tmp_path,monkeypatch):
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from sqlalchemy.exc import DBAPIError
    import app.artifacts as artifacts
    from app.artifacts import write_bytes
    from app.ingestion.vlr import save_match
    from app.research import generate_models
    from app.research.dataset import export_dataset
    from app.research.prospective import build_report
    from app.models import PipelineRun
    monkeypatch.setattr(artifacts,"ARTIFACT_ROOT",tmp_path)
    sessions = lambda:Session(bind=migrated_connection,join_transaction_mode="create_savepoint")
    now = datetime.now(timezone.utc)
    scheduled = now+timedelta(hours=2)
    data = {"vlr_id":987,"team1":{"vlr_id":981,"name":"Fixture A"},
            "team2":{"vlr_id":982,"name":"Fixture B"},"team1_score":None,"team2_score":None,
            "event_name":"Synthetic test only","stage":None,"status":"scheduled","scheduled_at":scheduled,
            "evidence":{"received_at":now.isoformat(),"raw_sha256":write_bytes("raw",b"synthetic scheduled"),
                        "source_url":"https://example.invalid/fixture"}}
    with sessions() as db:
        match = save_match(db,data)
        db.commit()
        mid = match.id
        save_match(db,data)
        db.commit()
        assert db.query(MatchObservation).count() == 1  # Retrying same retrieval is idempotent.
    def snapshot():
        with sessions() as db:
            return export_dataset(db,datetime.now(timezone.utc))
    monkeypatch.setattr(generate_models,"snapshot_current",snapshot)
    monkeypatch.setattr(generate_models,"SessionLocal",sessions)
    assert generate_models.generate(prospective=True)["created"] == 1
    assert generate_models.generate(prospective=True)["created"] == 0
    with sessions() as db:
        forecast = db.scalar(select(Forecast))
        assert forecast.team1_win_probability == 0.5
        assert "cold-start" in forecast.rationale
        frozen = (forecast.id,forecast.team1_win_probability,forecast.model_run_id)
        key,dataset = snapshot()
        _,pending = build_report(db,key,dataset)
        assert pending["counts"] == {"PENDING_RESULT":1}
        result_at = scheduled+timedelta(hours=1)
        raw = write_bytes("raw",b"synthetic completed")
        obs = MatchObservation(match_id=mid,received_at=result_at,ingested_at=result_at,
            raw_sha256=raw,source_url="https://example.invalid/fixture",
            payload={"team1_id":forecast.team1_id,"team2_id":forecast.team2_id,
                     "scheduled_at":scheduled.isoformat(),"status":"completed","team1_score":2,"team2_score":0})
        db.add(obs)
        db.flush()
        key,dataset = export_dataset(db,result_at+timedelta(seconds=1))
        report_key,report = build_report(db,key,dataset)
        assert report["counts"] == {"VERIFIED_PROSPECTIVE":1}
        model = report["models"][forecast.source_key]
        assert model["brier"] == 0.25 and model["calibration"] == []
        assert build_report(db,key,dataset)[0] == report_key
        # A tied correction removes the label from a later report, never the saved prediction.
        db.add(MatchObservation(match_id=mid,received_at=result_at+timedelta(minutes=1),
            ingested_at=result_at+timedelta(minutes=1),raw_sha256=raw,source_url=obs.source_url,
            payload={**obs.payload,"team2_score":2}))
        db.flush()
        key,dataset = export_dataset(db,result_at+timedelta(minutes=2))
        _,retracted = build_report(db,key,dataset)
        assert retracted["counts"] == {"INELIGIBLE_RESULT":1}
        assert not retracted["models"]
        assert (forecast.id,forecast.team1_win_probability,forecast.model_run_id) == frozen
        db.add(PipelineRun(id="0"*32,started_at=now,finished_at=now,status="SUCCEEDED",details={}))
        db.commit()
    with pytest.raises(DBAPIError,match="append-only"):
        with migrated_connection.begin_nested():
            migrated_connection.execute(text("DELETE FROM pipeline_runs"))


def test_source_migration_backfills_without_inventing_discovery(postgres_connection):
    c = postgres_connection
    config = migration_config(c)
    command.upgrade(config, "b72c904e1a36")
    c.execute(insert(Team), [{"id": 1, "vlr_id": 101, "name": "A"}, {"id": 2, "vlr_id": 102, "name": "B"}])
    c.execute(insert(Match).values(id=1, vlr_id=900, team1_id=1, team2_id=2))
    command.upgrade(config, "head")
    assert c.execute(text("SELECT match_id, source, external_id, first_seen_at FROM match_sources")).one() == (1, "vlr", "900", None)
    assert c.scalar(text("SELECT count(*) FROM team_source_identities")) == 2
    command.downgrade(config, "b72c904e1a36")
    assert c.scalar(text("SELECT vlr_id FROM matches WHERE id=1")) == 900


def test_thespike_only_forecasts_dedup_and_temporal_availability(migrated_connection, tmp_path, monkeypatch):
    from sqlalchemy.orm import Session
    import app.artifacts as artifacts
    from app.artifacts import write_bytes
    from app.ingestion.resolution import save_source_match
    from app.research import generate_models
    from app.research.dataset import export_dataset
    from app.models import MatchSource
    monkeypatch.setattr(artifacts, "ARTIFACT_ROOT", tmp_path)
    sessions = lambda: Session(bind=migrated_connection, join_transaction_mode="create_savepoint")
    now = datetime.now(timezone.utc)
    data = dict(source="thespike", external_id="148759", source_url="https://www.thespike.gg/test-fixture",
        team1={"external_id":"111", "name":"PCIFIC Esports"}, team2={"external_id":"222", "name":"Fear Never Ends"},
        scheduled_at=now + timedelta(hours=2), status="scheduled", event_name="Synthetic Monsters Reloaded", stage="Decider",
        team1_score=None, team2_score=None,
        evidence={"received_at": now.isoformat(), "raw_sha256": write_bytes("raw", b"synthetic upcoming only"), "source_url":"https://www.thespike.gg/test-fixture"})
    with sessions() as db:
        match = save_source_match(db, data)
        mid = match.id
        db.commit()
        assert match.vlr_id is None
    def snapshot():
        with sessions() as db: return export_dataset(db, datetime.now(timezone.utc))
    monkeypatch.setattr(generate_models, "snapshot_current", snapshot)
    monkeypatch.setattr(generate_models, "SessionLocal", sessions)
    assert generate_models.generate(prospective=True)["created"] == 1
    with sessions() as db:
        vlr = {**data, "source":"vlr", "external_id":"999", "team1":{"external_id":"1", "name":"PCIFIC Esports"}, "team2":{"external_id":"2", "name":"Fear Never Ends"}}
        assert save_source_match(db, vlr).id == mid
        db.commit()
        assert db.query(Match).count() == 1
        assert db.query(MatchSource).count() == 2
    assert generate_models.generate(prospective=True)["created"] == 0
    with sessions() as db:
        assert db.query(Forecast).count() == 1
        # A late imported result cannot appear in an earlier prediction snapshot.
        historical = {**data, "external_id":"historical", "scheduled_at":now-timedelta(days=2),
            "status":"completed", "team1_score":2, "team2_score":0,
            "evidence":{**data["evidence"], "raw_sha256":write_bytes("raw", b"synthetic recent result")}}
        save_source_match(db, historical)
        db.commit()
        _, before = export_dataset(db, now - timedelta(seconds=1))
        assert before["result_events"] == []
        _, after = export_dataset(db, datetime.now(timezone.utc))
        result = next(r for r in after["result_events"] if r["status"] == "completed")
        assert datetime.fromisoformat(result["result_observed_at"]) >= now


def test_multi_source_dry_run_rolls_back(migrated_connection):
    from sqlalchemy.orm import Session
    from types import SimpleNamespace
    from app.ingestion.multi_source import sync_sources
    sessions = lambda: Session(bind=migrated_connection, join_transaction_mode="create_savepoint")
    data = dict(source="thespike", external_id="fixture", team1={"external_id":"1", "name":"A"},
                team2={"external_id":"2", "name":"B"}, scheduled_at=LOCK_TIME + timedelta(days=1000),
                event_name="Synthetic", stage="Final", status="scheduled", team1_score=None, team2_score=None)
    source = SimpleNamespace(name="thespike", discover_upcoming_matches=lambda pages: iter([data]))
    result = sync_sources([source], dry_run=True, session_factory=sessions)
    assert result["created"] == 1
    assert migrated_connection.scalar(text("SELECT count(*) FROM matches")) == 0
    assert migrated_connection.scalar(text("SELECT count(*) FROM teams")) == 0


def test_source_tables_reuse_production_roles_and_block_public_access(postgres_connection):
    c = postgres_connection
    config = migration_config(c)
    command.upgrade(config, "b72c904e1a36")
    for role in ("cq_demo_api", "cq_demo_worker", "cq_app", "anon", "authenticated"):
        if not c.scalar(text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role":role}):
            c.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN')
    command.upgrade(config, "head")
    schema = c.scalar(text("SELECT current_schema()"))
    for table in ("match_sources", "team_source_identities", "team_aliases", "source_issues"):
        qualified = f'{schema}.{table}'
        assert c.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid=CAST(:tab AS regclass)"), {"tab":qualified})
        assert c.scalar(text("SELECT has_table_privilege('cq_demo_api',:tab,'SELECT')"), {"tab":qualified})
        assert not c.scalar(text("SELECT has_table_privilege('cq_demo_api',:tab,'INSERT')"), {"tab":qualified})
        assert c.scalar(text("SELECT has_table_privilege('cq_demo_worker',:tab,'INSERT')"), {"tab":qualified})
        assert c.scalar(text("SELECT has_table_privilege('cq_app',:tab,'INSERT')"), {"tab":qualified})
        assert not c.scalar(text("SELECT has_table_privilege('anon',:tab,'SELECT')"), {"tab":qualified})
        assert not c.scalar(text("SELECT has_table_privilege('authenticated',:tab,'SELECT')"), {"tab":qualified})
        assert c.scalar(text("SELECT count(*) FROM pg_policies WHERE schemaname=:ns AND tablename=:tab"), {"ns":schema,"tab":table}) == 3


def test_source_migration_preserves_all_historical_relationships(postgres_connection):
    from app.models import MatchMap, PlayerMapStat
    c = postgres_connection
    config = migration_config(c)
    command.upgrade(config, "b72c904e1a36")
    c.execute(insert(Team), [{"id":1,"vlr_id":11,"name":"A"},{"id":2,"vlr_id":22,"name":"B"}])
    c.execute(insert(Player).values(id=1,vlr_id=33,handle="historical-player"))
    c.execute(insert(Match).values(id=1,vlr_id=44,team1_id=1,team2_id=2,status="completed",team1_score=2,team2_score=0,scheduled_at=LOCK_TIME))
    c.execute(insert(MatchMap).values(id=1,vlr_game_id=55,match_id=1,map_number=1,map_name="Ascent",team1_score=13,team2_score=5))
    c.execute(insert(PlayerMapStat).values(id=1,match_map_id=1,player_id=1,team_id=1,kills_all=20,deaths_all=10))
    c.execute(insert(ModelRun).values(id="a"*64,source_key="model:elo:v1",dataset_sha256="b"*64,configuration={},created_at=CREATED_AT))
    c.execute(insert(Forecast).values(id=1,match_id=1,team1_id=1,team2_id=2,source_type="model",source_key="model:elo:v1",team1_win_probability=.6,created_at=CREATED_AT,lock_time=LOCK_TIME,model_run_id="a"*64))
    tables=("teams","players","matches","match_maps","player_map_stats","forecasts","model_runs")
    before={t:c.execute(text(f'SELECT * FROM {t} ORDER BY id')).all() for t in tables}
    command.upgrade(config,"head")
    command.upgrade(config,"head")
    after={t:c.execute(text(f'SELECT * FROM {t} ORDER BY id')).all() for t in tables}
    assert after == before
    assert c.scalar(text('SELECT count(*) FROM match_sources')) == 1
    assert c.scalar(text('SELECT count(*) FROM team_source_identities')) == 2
