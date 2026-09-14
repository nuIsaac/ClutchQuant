"""Score the forecasts that were actually frozen, never hindsight replays."""
from collections import Counter, defaultdict

from sqlalchemy import select

from app.artifacts import digest, read_bytes, read_json, write_json
from app.models import Forecast, ModelRun
from app.research.dataset import utc
from app.research.evaluation import metrics
from app.scoring import calculate_brier_score, calculate_log_loss


def verify_forecast(forecast, run):
    if run is None or run.configuration.get("protocol") != "prospective-v1":
        return "UNVERIFIED_LEGACY_OR_EXPERIMENT"
    manifest = read_json("runs",run.id)
    dataset = read_json("datasets",run.dataset_sha256)
    schedule = manifest.get("schedule_observation")
    if (manifest != run.configuration or manifest["dataset_sha256"] != run.dataset_sha256
            or manifest["model"]["source_key"] != forecast.source_key
            or manifest["match_id"] != forecast.match_id
            or (manifest["team1_id"],manifest["team2_id"]) != (forecast.team1_id,forecast.team2_id)
            or manifest["probability"] != forecast.team1_win_probability
            or utc(manifest["lock_time"]) != utc(forecast.lock_time)
            or not utc(dataset["as_of"]) == utc(manifest["training_cutoff"])
            or not utc(manifest["training_cutoff"]) <= utc(manifest["prediction_at"]) <= utc(forecast.created_at) < utc(forecast.lock_time)
            or not schedule or schedule not in dataset["result_events"]
            or schedule["id"] != forecast.match_id or schedule["status"] != "scheduled"
            or (schedule["team1_id"],schedule["team2_id"]) != (forecast.team1_id,forecast.team2_id)
            or utc(schedule["scheduled_at"]) != utc(forecast.lock_time)):
        return "INVALID_FREEZE_EVIDENCE"
    if any(utc(event["result_observed_at"]) > utc(dataset["as_of"]) for event in dataset["result_events"]):
        return "INPUT_AFTER_CUTOFF"
    for key in dataset["raw_sha256"]:
        if digest(read_bytes("raw",key)) != key:
            raise ValueError("Raw evidence integrity failure")
    return None


def score_frozen(forecast, run, events, as_of):
    reason = verify_forecast(forecast,run)
    if reason:
        return {"status":reason}
    observed = sorted((e for e in events if e["id"] == forecast.match_id
                       and utc(e["result_observed_at"]) <= as_of),
                      key=lambda e:(utc(e["result_observed_at"]),e["observation_id"]))
    if not observed:
        return {"status":"PENDING_RESULT"}
    result = observed[-1]
    if result["exclusion_reason"] is not None:
        return {"status":"PENDING_RESULT" if result["status"] != "completed" else "INELIGIBLE_RESULT",
                "reason":result["exclusion_reason"],"result_observation_id":result["observation_id"]}
    if (utc(result["scheduled_at"]) <= utc(forecast.created_at)
            or any(e["status"] == "completed" and utc(e["result_observed_at"]) <= utc(forecast.created_at) for e in observed)):
        return {"status":"RESULT_OR_START_BEFORE_FORECAST"}
    a,b = result["team1_id"],result["team2_id"]
    if {a,b} != {forecast.team1_id,forecast.team2_id}:
        return {"status":"PARTICIPANTS_CHANGED"}
    first,second = result["team1_score"],result["team2_score"]
    if a != forecast.team1_id:
        first,second = second,first
    return {"status":"VERIFIED_PROSPECTIVE", "outcome":int(first > second),
            "brier":calculate_brier_score(forecast.team1_win_probability,int(first > second)),
            "log_loss":calculate_log_loss(forecast.team1_win_probability,int(first > second)),
            "team1_score":first,"team2_score":second,
            "result_observation_id":result["observation_id"],
            "result_available_at":result["result_observed_at"],"result_raw_sha256":result["raw_sha256"]}


def build_report(db, dataset_key, dataset):
    records,groups = [],defaultdict(list)
    for forecast,run in db.execute(select(Forecast,ModelRun).outerjoin(ModelRun,Forecast.model_run_id==ModelRun.id).order_by(Forecast.id)):
        if utc(forecast.created_at) > utc(dataset["as_of"]):
            continue
        row = {"forecast_id":forecast.id,"match_id":forecast.match_id,
               "team1_id":forecast.team1_id,"team2_id":forecast.team2_id,
               "source_key":forecast.source_key,"probability":forecast.team1_win_probability,
               "created_at":utc(forecast.created_at).isoformat(),"lock_time":utc(forecast.lock_time).isoformat(),
               "model_run_id":forecast.model_run_id,
               **score_frozen(forecast,run,dataset["result_events"],utc(dataset["as_of"]))}
        records.append(row)
        if row["status"] == "VERIFIED_PROSPECTIVE":
            groups[row["source_key"]].append(row)
    models = {}
    for source,rows in groups.items():
        values = metrics(rows)
        sufficient = len(rows) >= 100
        if not sufficient:
            values.update(calibration=[],ece=None)
        models[source] = {**values,"calibration_status":"DESCRIPTIVE" if sufficient else "INSUFFICIENT_SAMPLE",
                          "interpretation":"Descriptive prospective scores, not evidence of superiority"}
    report = {"protocol":"verified-prospective-v1","as_of":dataset["as_of"],
              "dataset_sha256":dataset_key,"models":models,"records":records,
              "counts":dict(Counter(row["status"] for row in records)),
              "categories":{"legacy":"Unverified legacy forecasts; excluded from prospective metrics",
                            "historical_experiments":"Separate replay reports; never combined here",
                            "prospective":"Actual frozen predictions with checked observation provenance"}}
    return write_json("reports",report),report
