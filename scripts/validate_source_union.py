"""Synthetic union report, isolated schema, always removed.

Run from apps/api with PYTHONPATH=. and TEST_DATABASE_URL set:
  .venv/bin/python ../../scripts/validate_source_union.py
No live collection, application tables or production targets are inferred.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from alembic import command
from alembic.config import Config

from app import artifacts
from app.artifacts import write_bytes
from app.ingestion.multi_source import sync_sources
from app.research import generate_models
from app.research.dataset import export_dataset

url = os.environ["TEST_DATABASE_URL"]
engine = create_engine(url)
schema = "clutchquant_validation_" + uuid4().hex
with engine.begin() as c:
    c.execute(CreateSchema(schema))
try:
    with tempfile.TemporaryDirectory() as directory, patch.object(artifacts, "ARTIFACT_ROOT", Path(directory)):
        with engine.connect() as c, c.begin():
            c.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            config = Config("alembic.ini")
            config.attributes["connection"] = c
            command.upgrade(config, "head")
            sessions = lambda: Session(bind=c, join_transaction_mode="create_savepoint")
            now = datetime.now(timezone.utc)
            def record(source, mid, offset):
                return dict(source=source, external_id=str(mid),
                    team1={"external_id":"1" if source == "vlr" else "11", "name":"Synthetic A"},
                    team2={"external_id":"2" if source == "vlr" else "22", "name":"Synthetic B"},
                    scheduled_at=now+timedelta(days=offset), event_name="Synthetic validation", stage="Final",
                    status="scheduled", team1_score=None, team2_score=None,
                    evidence={"received_at":now.isoformat(), "raw_sha256":write_bytes("raw", f"synthetic {source} {mid}".encode()),
                              "source_url":f"https://www.{source}.gg/{mid}"})
            sources = [SimpleNamespace(name="vlr", discover_upcoming_matches=lambda pages:iter([record("vlr",101,1),record("vlr",102,2)])),
                       SimpleNamespace(name="thespike", discover_upcoming_matches=lambda pages:iter([record("thespike",201,1),record("thespike",202,3)]))]
            report = sync_sources(sources, dry_run=True, session_factory=sessions)
            assert c.scalar(text("SELECT count(*) FROM matches")) == 0
            # The second pass is committed only inside this disposable schema.
            sync_sources(sources, session_factory=sessions)
            def snapshot():
                with sessions() as db: return export_dataset(db, datetime.now(timezone.utc))
            with patch.object(generate_models,"SessionLocal",sessions), patch.object(generate_models,"snapshot_current",snapshot):
                first = generate_models.generate(prospective=True)
                second = generate_models.generate(prospective=True)
            report.update(validation="synthetic only; not live coverage", forecasts_generated=first["created"], duplicate_forecasts_generated=second["created"])
            assert report["coverage"]["upcoming"] == dict(canonical_total=3,vlr_only=1,thespike_only=1,both=1,unmapped=0)
            assert first["created"] == 3 and second["created"] == 0
            print(json.dumps(report, indent=2))
finally:
    with engine.begin() as c:
        c.execute(DropSchema(schema, cascade=True))
    engine.dispose()
