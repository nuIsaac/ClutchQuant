"""Aggregate coverage and per-match public provenance; no raw payloads/secrets."""
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.ingestion.multi_source import coverage
from app.models import MatchSource

router = APIRouter(prefix="/api/v1/data", tags=["data coverage"])


@router.get("/coverage")
def data_coverage(db: Annotated[Session, Depends(get_db)]):
    return coverage(db)


@router.get("/matches/{match_id}/sources")
def match_sources(match_id: int, db: Annotated[Session, Depends(get_db)]):
    return [{"source": s.source, "external_id": s.external_id, "source_url": s.source_url,
             "last_synced_at": s.last_synced_at}
            for s in db.scalars(select(MatchSource).where(MatchSource.match_id == match_id))]
