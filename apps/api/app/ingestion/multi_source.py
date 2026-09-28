"""Bounded upcoming union; each record and source has an independent failure boundary."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import Match, MatchSource, SourceIssue, Forecast
from app.ingestion.resolution import save_source_match, UnresolvedTeam, issue

log = logging.getLogger(__name__)


def coverage(db):
    now = datetime.now(timezone.utc)
    result = {}
    for label, query in (
        ("upcoming", select(Match.id).where(Match.status == "scheduled", Match.scheduled_at > now)),
        ("recent_completed", select(Match.id).where(Match.status == "completed", Match.scheduled_at >= now - timedelta(days=7))),
    ):
        ids = set(db.scalars(query))
        sources = {mid: set() for mid in ids}
        if ids:
            for mid, name in db.execute(select(MatchSource.match_id, MatchSource.source).where(MatchSource.match_id.in_(ids))):
                sources[mid].add(name)
        result[label] = {"canonical_total": len(ids), "vlr_only": sum(s == {"vlr"} for s in sources.values()),
                         "thespike_only": sum(s == {"thespike"} for s in sources.values()),
                         "both": sum({"vlr", "thespike"} <= s for s in sources.values()),
                         "unmapped": sum(not s for s in sources.values())}
        if label == "upcoming":
            forecasted = set(db.scalars(select(Forecast.match_id).where(Forecast.match_id.in_(ids)))) if ids else set()
            result["forecasts_awaiting_data"] = len(ids - forecasted)
    result["open_issues"] = dict(db.execute(select(SourceIssue.kind, func.count()).where(
        SourceIssue.resolved_at.is_(None)).group_by(SourceIssue.kind)).all())
    return result


def sync_sources(sources, *, pages=1, dry_run=False, session_factory=SessionLocal):
    report = {"sources": {}, "saved": 0, "failed": 0, "unresolved": 0, "created": 0, "matched": 0}
    with session_factory() as db:
        report["existing_canonical_matches"] = db.scalar(select(func.count()).select_from(Match))
        for source in sources:
            counts = {"discovered": 0, "saved": 0, "failed": 0}
            report["sources"][source.name] = counts
            try:
                for data in source.discover_upcoming_matches(pages):
                    counts["discovered"] += 1
                    external = str(data.get("external_id") or data.get("vlr_id") or "unknown")
                    if data.get("collection_error"):
                        counts["failed"] += 1
                        report["failed"] += 1
                        issue(db, source.name, external, "INGESTION_FAILURE", {"operation": "fetch_match", "exception": data["collection_error"], "retry": "next cycle"})
                        continue
                    try:
                        before = db.scalar(select(func.count()).select_from(Match))
                        with db.begin_nested():
                            save_source_match(db, data)
                        after = db.scalar(select(func.count()).select_from(Match))
                        report["created" if after > before else "matched"] += 1
                        counts["saved"] += 1
                        report["saved"] += 1
                    except UnresolvedTeam as error:
                        report["unresolved"] += 1
                        issue(db, source.name, external, "UNRESOLVED_TEAM", {"reason": str(error)})
                    except Exception as error:
                        counts["failed"] += 1
                        report["failed"] += 1
                        issue(db, source.name, external, "INGESTION_FAILURE", {"operation": "resolve", "exception": type(error).__name__, "retry": "next cycle"})
            except Exception as error:
                counts["failed"] += 1
                report["failed"] += 1
                issue(db, source.name, "discovery", "INGESTION_FAILURE", {"operation": "discover", "exception": type(error).__name__, "retry": "next cycle"})
            log.info("[%s] discovered=%s saved=%s failed=%s", source.name.upper(), counts["discovered"], counts["saved"], counts["failed"])
        db.flush()
        report["coverage"] = coverage(db)
        report["dry_run"] = dry_run
        if dry_run:
            db.rollback()
        else:
            db.commit()
    return report


def configured_sources(selection="all"):
    from app.data_sources.vlr import VlrSource
    from app.data_sources.thespike import ThespikeSource
    sources = []
    if selection in {"all", "vlr"}:
        sources.append(VlrSource())
    if selection == "thespike" or (selection == "all" and os.getenv("THESPIKE_EXPORT_PATH")):
        sources.append(ThespikeSource())
    if selection == "all" and not os.getenv("THESPIKE_EXPORT_PATH"):
        log.warning("[THESPIKE] disabled: authorized export not configured")
    return sources


def sync_upcoming_matches(max_pages=1):
    return sync_sources(configured_sources(), pages=max_pages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["all", "vlr", "thespike"], default="all")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.pages <= 10:
        parser.error("pages must be 1..10")
    logging.basicConfig(level=logging.INFO)
    result = sync_sources(configured_sources(args.source), pages=args.pages, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["failed"] else 0)


if __name__ == "__main__":
    main()
