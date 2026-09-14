from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.artifacts import read_json
from app.dependencies import get_db
from app.models import MatchObservation, ModelRun, PipelineRun
from app.research.online_models import CONFIGS, FEATURE_NAMES, FEATURE_VERSION

router = APIRouter(prefix="/api/v1/research",tags=["research"])
DB = Annotated[Session,Depends(get_db)]


@router.get("/prospective")
def prospective_report(db: DB, limit: int = Query(50,ge=1,le=200), offset: int = Query(0,ge=0)):
    latest = db.scalar(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1))
    scored = db.scalar(select(PipelineRun).where(PipelineRun.report_sha256.is_not(None)).order_by(PipelineRun.started_at.desc()).limit(1))
    state = {"last_run_at":latest.finished_at if latest else None,
             "last_run_status":latest.status if latest else "NOT_STARTED"}
    if scored is None:
        return {**state,"as_of":None,"models":{},"records":[],"counts":{},"total":0}
    try:
        report = read_json("reports",scored.report_sha256)
    except (FileNotFoundError,ValueError) as error:
        raise HTTPException(status_code=503,detail="Prospective report unavailable or corrupt") from error
    rows = list(reversed(report["records"]))
    return {**state,**report,"report_sha256":scored.report_sha256,"total":len(rows),
            "records":rows[offset:offset+limit]}


@router.get("/models")
def models(db: DB):
    latest = db.scalar(select(func.max(MatchObservation.ingested_at)))
    return {
        "models":[{"name":name,**config,"experimental":name != "elo_v1"} for name,config in CONFIGS.items()],
        "feature_version":FEATURE_VERSION,"features":FEATURE_NAMES,
        "latest_observation_at":latest,
        "historical_availability":"UNKNOWN for records without observations",
        "ensemble_status":"Not promoted; requires supporting evaluation and explicit operator action",
    }


@router.get("/runs/{run_id}")
def run_details(db: DB,run_id: str = Path(pattern=r"^[a-f0-9]{64}$")):
    run = db.get(ModelRun,run_id)
    if run is None:
        raise HTTPException(status_code=404,detail="Model run not found")
    return {"id":run.id,"source_key":run.source_key,"dataset_sha256":run.dataset_sha256,
            "created_at":run.created_at,"configuration":run.configuration}


@router.get("/reports/{report_id}")
def report_details(report_id: str = Path(pattern=r"^[a-f0-9]{64}$")):
    try:
        report = read_json("reports",report_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404,detail="Report not found") from error
    except ValueError as error:
        raise HTTPException(status_code=503,detail="Report integrity check failed") from error
    return {key:value for key,value in report.items() if key != "predictions"}
