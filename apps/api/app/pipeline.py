"""One locked cycle, suitable for a local worker or an external scheduler."""
import argparse
from datetime import datetime, timezone
import json
import logging
import signal
import threading
from uuid import uuid4

from sqlalchemy import text, select

from app.artifacts import write_json
from app.database import engine, SessionLocal
from app.ingestion.vlr_upcoming import sync_upcoming_matches
from app.ingestion.vlr_recent import sync_recent_results
from app.models import PipelineRun
from app.research.generate_models import generate, snapshot_current
from app.research.prospective import build_report

logger = logging.getLogger(__name__)
LOCK_ID = 731940271


def run_cycle(*, pages=1, experimental=False, collect=True, forecast_first=False):
    started = datetime.now(timezone.utc)
    run_id = uuid4().hex
    details = {"run_id":run_id,"started_at":started.isoformat(),"collection_enabled":collect,
               "order":"forecast-first" if forecast_first else "results-first","steps":{}}
    report_key = None
    status = "FAILED"
    # Session advisory lock spans the whole cycle, across independent transactions.
    with engine.connect() as guard:
        if not guard.scalar(text("SELECT pg_try_advisory_lock(:id)"),{"id":LOCK_ID}):
            return {"status":"SKIPPED_OVERLAP"}
        try:
            write_json("jobs",{**details,"status":"STARTED"})
            def collect_step(name, job):
                result = job()
                details["steps"][name] = result
                if result["failed"]:
                    raise RuntimeError(f"{name} collection reported failures; cycle stopped")
            if collect:
                if not forecast_first:
                    collect_step("results",lambda:sync_recent_results(pages))
                collect_step("upcoming",lambda:sync_upcoming_matches(pages))
            details["steps"]["forecasts"] = generate(experimental,prospective=True)
            if collect and forecast_first:
                collect_step("results",lambda:sync_recent_results(pages))
            key,dataset = snapshot_current()
            with SessionLocal() as db:
                report_key,report = build_report(db,key,dataset)
            details["steps"]["scoring"] = {"report_sha256":report_key,"counts":report["counts"]}
            status = "SUCCEEDED"
        except Exception as error:
            logger.exception("Pipeline failed",extra={"run_id":run_id})
            details["error_type"] = type(error).__name__
            status = "FAILED"
        finally:
            try:
                finished = datetime.now(timezone.utc)
                details.update(status=status,finished_at=finished.isoformat())
                write_json("jobs",details)
                with SessionLocal() as db:
                    db.add(PipelineRun(id=run_id,started_at=started,finished_at=finished,
                                       status=status,report_sha256=report_key,details=details))
                    db.commit()
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:id)"),{"id":LOCK_ID})
    return details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--demo-cycle",action="store_true",help="With --once: freeze before collecting completed results")
    parser.add_argument("--interval-seconds",type=int,default=300)
    parser.add_argument("--pages",type=int,default=1)
    parser.add_argument("--experimental",action="store_true")
    parser.add_argument("--no-collect",action="store_true",help="Use existing fresh evidence; useful for smoke checks")
    parser.add_argument("--health",action="store_true",help="Exit successfully only after a recent successful cycle")
    args = parser.parse_args()
    if args.demo_cycle and not args.once:
        parser.error("--demo-cycle requires --once; persistent worker behavior is unchanged")
    if args.health:
        with SessionLocal() as db:
            run = db.scalar(select(PipelineRun).where(PipelineRun.details["collection_enabled"].as_boolean().is_(True)).order_by(PipelineRun.started_at.desc()).limit(1))
            healthy = (run is not None and run.status == "SUCCEEDED"
                       and (datetime.now(timezone.utc)-run.finished_at).total_seconds() < 900)
        raise SystemExit(0 if healthy else 1)
    if not 1 <= args.pages <= 10 or args.interval_seconds < 60:
        parser.error("pages must be 1..10 and interval at least 60 seconds")
    logging.basicConfig(level=logging.INFO)
    stop = threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,lambda *_:stop.set())
    while not stop.is_set():
        result = run_cycle(pages=args.pages,experimental=args.experimental,collect=not args.no_collect,
                           forecast_first=args.demo_cycle)
        print(json.dumps(result),flush=True)
        if args.once:
            raise SystemExit(1 if result["status"] == "FAILED" else 0)
        stop.wait(args.interval_seconds)


if __name__ == "__main__":
    main()
