"""Bounded upcoming union; each record and source has an independent failure boundary."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import time
from sqlalchemy import select, func
from app.database import SessionLocal
from app.models import Match, MatchSource, SourceIssue, Forecast, TeamSourceIdentity
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
    sources = list(sources)
    started = time.monotonic()
    log.info("INGESTION_START sources=%s dry_run=%s", [s.name for s in sources], dry_run)
    report = {"sources": {}, "saved": 0, "failed": 0, "unresolved": 0, "created": 0, "matched": 0}
    with session_factory() as db:
        report["existing_canonical_matches"] = db.scalar(select(func.count()).select_from(Match))
        for source in sources:
            counts = {"discovered": 0, "saved": 0, "failed": 0, "created": 0, "matched": 0,
                      "unresolved": 0, "persistence_failures": 0, "parse_failures": 0}
            mapping_before = db.scalar(select(func.count()).select_from(MatchSource).where(MatchSource.source == source.name))
            team_mapping_before = db.scalar(select(func.count()).select_from(TeamSourceIdentity).where(TeamSourceIdentity.source == source.name))
            report["sources"][source.name] = counts
            try:
                for data in source.discover_upcoming_matches(pages):
                    counts["discovered"] += 1
                    external = str(data.get("external_id") or data.get("vlr_id") or "unknown")
                    if data.get("collection_error"):
                        counts["failed"] += 1
                        counts["parse_failures"] += 1
                        report["failed"] += 1
                        issue(db, source.name, external, "INGESTION_FAILURE", {"operation": "fetch_match", "exception": data["collection_error"], "retry": "next cycle"})
                        continue
                    try:
                        before = db.scalar(select(func.count()).select_from(Match))
                        with db.begin_nested():
                            save_source_match(db, data)
                        after = db.scalar(select(func.count()).select_from(Match))
                        outcome = "created" if after > before else "matched"
                        report[outcome] += 1
                        counts[outcome] += 1
                        counts["saved"] += 1
                        report["saved"] += 1
                    except UnresolvedTeam as error:
                        report["unresolved"] += 1
                        counts["unresolved"] += 1
                        issue(db, source.name, external, "UNRESOLVED_TEAM", {"reason": str(error)})
                    except Exception as error:
                        counts["persistence_failures"] += 1
                        counts["failed"] += 1
                        report["failed"] += 1
                        issue(db, source.name, external, "INGESTION_FAILURE", {"operation": "resolve", "exception": type(error).__name__, "retry": "next cycle"})
            except Exception as error:
                counts["failed"] += 1
                report["failed"] += 1
                issue(db, source.name, "discovery", "INGESTION_FAILURE", {"operation": "discover", "exception": type(error).__name__, "retry": "next cycle"})
            counts.update(getattr(source, "metrics", {}))
            counts["match_mappings_created"] = db.scalar(select(func.count()).select_from(MatchSource).where(MatchSource.source == source.name)) - mapping_before
            counts["team_mappings_created"] = db.scalar(select(func.count()).select_from(TeamSourceIdentity).where(TeamSourceIdentity.source == source.name)) - team_mapping_before
            log.info("SOURCE_SUMMARY source=%s counts=%s", source.name, json.dumps(counts, sort_keys=True))
        db.flush()
        report["coverage"] = coverage(db)
        report["dry_run"] = dry_run
        if dry_run:
            db.rollback()
        else:
            db.commit()
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    log.info("INGESTION_END saved=%s failed=%s unmatched=%s duration_seconds=%s", report["saved"], report["failed"], report["unresolved"], report["duration_seconds"])
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
        log.info("[THESPIKE] disabled: authorized export not configured")
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
    logging.getLogger("httpx").setLevel(logging.WARNING)
    result = sync_sources(configured_sources(args.source), pages=args.pages, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["failed"] else 0)


if __name__ == "__main__":
    main()
