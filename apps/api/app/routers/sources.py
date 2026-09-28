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


@router.get("/health")
def data_health(db: Annotated[Session, Depends(get_db)]):
    """Sanitized operational summary from existing scheduled pipeline receipts.

    No raw issue payloads, artifact keys, environment values or exception text.
    Disabled THESPIKE is normal; it does not degrade VLR's status.
    """
    from datetime import datetime, timezone
    from sqlalchemy import func
    from app.models import Match, PipelineRun
    now = datetime.now(timezone.utc)
    runs = db.scalars(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(100)).all()
    collection = [r for r in runs if r.details.get("collection_enabled")]
    latest = collection[0] if collection else None
    def stamp(value):
        if value is None: return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    source_status = {}
    allowed_counts = {"discovered", "saved", "failed", "created", "matched", "unresolved", "fetched",
                      "parsed", "not_forecastable", "parse_failures", "persistence_failures",
                      "match_mappings_created", "team_mappings_created"}
    for name in ("vlr", "thespike"):
        attempts = [(r, r.details.get("steps", {}).get("upcoming", {}).get("sources", {}).get(name)) for r in collection]
        attempts = [(r, c) for r, c in attempts if isinstance(c, dict)]
        last = attempts[0] if attempts else None
        success = next((r for r, c in attempts if not c.get("failed") and not c.get("unresolved")), None)
        last_success = stamp(success.finished_at) if success else None
        age = max(0, (now-last_success).total_seconds()) if last_success else None
        active_latest = bool(latest and name in latest.details.get("steps", {}).get("upcoming", {}).get("sources", {}))
        state = "disabled" if name == "thespike" and not active_latest else "unknown"
        if active_latest and last:
            state = "unavailable" if last[1].get("failed") and not last[1].get("saved") else "partial" if last[1].get("failed") or last[1].get("unresolved") else "ok"
            if state == "ok" and age is not None and age > 4*3600:
                state = "stale"  # Existing scheduler interval: three hours.
        source_status[name] = {"status": state, "last_attempt_at": stamp(last[0].started_at) if last else None,
                               "last_success_at": last_success, "age_seconds": age,
                               "counts": {k:v for k,v in (last[1] if last else {}).items() if k in allowed_counts}}
    total, oldest, newest = db.execute(select(func.count(Match.id), func.min(Match.scheduled_at), func.max(Match.scheduled_at))).one()
    forecasts = latest.details.get("steps", {}).get("forecasts", {}) if latest else {}
    return {"observed_at": now, "scope": "last 100 scheduled pipeline receipts; disabled sources are not failures",
            "last_attempt_at": stamp(latest.started_at) if latest else None,
            "last_run_status": latest.status if latest else None, "sources": source_status,
            "forecasts": {k:v for k,v in forecasts.items() if k in {"status", "created", "skipped", "duplicates_prevented"}},
            "history": {"matches": total, "oldest_match_at": oldest, "latest_match_at": newest},
            "coverage": coverage(db)}
