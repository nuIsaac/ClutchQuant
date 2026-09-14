"""Generate auditable forecasts; candidates require an explicit experimental flag."""

import argparse
from datetime import datetime, timezone
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artifacts import read_json, write_json
from app.database import engine, SessionLocal
from app.models import Forecast, Match, ModelRun
from app.research.dataset import code_identity, export_dataset, utc
from app.research.evaluation import history_rows, replay
from app.research.online_models import (CONFIGS, ENSEMBLE_COMPONENTS, EloState, FormState,
                                        fit_classifier, classifier_probability, FEATURE_NAMES)


def prepare(dataset, *, allow_cold_start=False):
    cutoff = utc(dataset["as_of"])
    history = [r for r in history_rows(dataset,cutoff)
               if utc(r["scheduled_at"]) < utc(r["result_observed_at"])]
    if not history and not allow_cold_start:
        return None
    states = {name:EloState(cfg["half_life_days"]) for name,cfg in CONFIGS.items() if cfg["family"] == "elo"}
    form = FormState()
    for row in history:
        at = utc(row["result_observed_at"])
        a,b = row["team1_id"],row["team2_id"]
        outcome = int(row["team1_score"] > row["team2_score"])
        form.learn(a,b,outcome,utc(row["scheduled_at"]),states["elo_v1"].rating(b,at),states["elo_v1"].rating(a,at))
        for state in states.values():
            state.learn(a,b,outcome,at)
    records,_ = replay(dataset,include_unscored=True,fit_models=False)
    fit_cutoff = cutoff.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    known = {r["id"]:r for r in history_rows(dataset,fit_cutoff)}
    training = []
    for row in records:
        event = known.get(row["match_id"])
        if (event is not None and utc(row["prediction_at"]) < fit_cutoff
                and (event["team1_id"],event["team2_id"]) == (row["team1_id"],row["team2_id"])):
            training.append({"features":row["features"],"outcome":int(event["team1_score"] > event["team2_score"])})
    classifiers = {name:fit_classifier(name,[r["features"] for r in training],
                                      [r["outcome"] for r in training])
                   for name in ("logistic_v1","boosting_v1")}
    return states,form,classifiers,len(history)


def snapshot_current():
    cutoff = datetime.now(timezone.utc)
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c:
        with c.begin():
            c.exec_driver_sql("SET TRANSACTION READ ONLY")
            with Session(bind=c) as db:
                    dataset_key,dataset = export_dataset(db,cutoff)
    return dataset_key,dataset


def schedule_evidence(dataset, match, at, max_age_seconds):
    events = [r for r in dataset.get("result_events", []) if r["id"] == match.id]
    if not events:
        return None
    latest = max(events, key=lambda r:(utc(r["result_observed_at"]),r["observation_id"]))
    available = utc(latest["result_observed_at"])
    if (latest["status"] != "scheduled" or latest.get("scheduled_at") is None
            or (latest["team1_id"],latest["team2_id"]) != (match.team1_id,match.team2_id)
            or utc(latest["scheduled_at"]) != utc(match.scheduled_at)
            or not 0 <= (at - available).total_seconds() <= max_age_seconds
            or utc(match.scheduled_at) <= at):
        return None
    return latest


def generate(experimental=False, ensemble_report=None, *, prospective=False, max_schedule_age_seconds=900):
    dataset_key,dataset = snapshot_current()
    cutoff = utc(dataset["as_of"])
    prepared = prepare(dataset, allow_cold_start=prospective)
    if prepared is None:
        return {"status":"BLOCKED","reason":"No result-availability evidence for training", "created":0,"dataset_sha256":dataset_key}
    states,form,classifiers,history_count = prepared
    identity = code_identity()
    if ensemble_report:
        report = read_json("reports",ensemble_report)
        if (not experimental or not report["ensemble"]["evidence_supports_review"]
                or report["code"]["source_sha256"] != identity["source_sha256"]
                or report["configurations"] != CONFIGS):
            raise ValueError("Ensemble requires experimental mode and supporting evidence for this exact implementation")
    created,skipped = 0,0
    with SessionLocal() as db:
        # Prevent concurrent schedule/team changes while the batch snapshots
        # deadlines. Expensive training has already finished outside this lock.
        upcoming = db.scalars(select(Match).where(
            Match.status == "scheduled", Match.scheduled_at > datetime.now(timezone.utc),
            Match.team1_id != Match.team2_id,
        ).order_by(Match.scheduled_at,Match.id).with_for_update()).all()
        for match in upcoming:
            at = datetime.now(timezone.utc)
            evidence = schedule_evidence(dataset,match,at,max_schedule_age_seconds) if prospective else None
            if prospective and evidence is None:
                skipped += 1
                continue
            features = form.features(match.team1_id,match.team2_id,at,states["elo_v1"])
            probabilities = {name:state.predict(match.team1_id,match.team2_id,at) for name,state in states.items()
                             if experimental or name == "elo_v1"}
            if experimental:
                probabilities.update({name:classifier_probability(model,features) for name,model in classifiers.items() if model is not None})
            if ensemble_report and all(name in probabilities for name in ENSEMBLE_COMPONENTS):
                probabilities["ensemble_v1"] = sum(probabilities[n] for n in ENSEMBLE_COMPONENTS)/len(ENSEMBLE_COMPONENTS)
            for name,probability in probabilities.items():
                config = CONFIGS.get(name,{"source_key":"model:ensemble:v1:observed-v1","components":list(ENSEMBLE_COMPONENTS)})
                source = config["source_key"]
                if prospective:
                    source = source.replace(":observed-v1", ":prospective-v1")
                    config = {**config,"source_key":source}
                if db.scalar(select(Forecast.id).where(Forecast.match_id==match.id,Forecast.source_key==source)):
                    skipped += 1
                    continue
                made_at = datetime.now(timezone.utc)
                if made_at >= utc(match.scheduled_at):
                    skipped += 1
                    continue
                manifest = {"model":config,"code":identity,"dataset_sha256":dataset_key,
                            "protocol":"prospective-v1" if prospective else "observed-v1",
                            "schedule_observation":evidence,
                            "lock_time":utc(match.scheduled_at).isoformat(),
                            "training_cutoff":cutoff.isoformat(),"prediction_at":at.isoformat(),
                            "features":dict(zip(FEATURE_NAMES,features)),"history_count":history_count,
                            "experimental":name != "elo_v1","ensemble_report":ensemble_report,
                            "match_id":match.id,"team1_id":match.team1_id,"team2_id":match.team2_id,
                            "probability":probability}
                run_id = write_json("runs",manifest)
                if db.get(ModelRun,run_id) is None:
                    db.add(ModelRun(id=run_id,source_key=source,dataset_sha256=dataset_key,
                                    configuration=manifest,created_at=made_at))
                    db.flush()
                db.add(Forecast(match_id=match.id,team1_id=match.team1_id,team2_id=match.team2_id,
                                source_type="model",source_key=source,team1_win_probability=probability,
                                model_run_id=run_id,created_at=made_at,lock_time=match.scheduled_at,
                                rationale=f"{name}; {history_count} observed historical results; "
                                          + ("cold-start 1500 prior; " if history_count == 0 else "")
                                          + ("experimental, not promoted" if name != "elo_v1" else "frozen Elo v1 formula")))
                created += 1
        db.commit()
    return {"status":"GENERATED","created":created,"skipped":skipped,"dataset_sha256":dataset_key}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experimental",action="store_true")
    parser.add_argument("--ensemble-report")
    parser.add_argument("--prospective",action="store_true")
    args = parser.parse_args()
    print(json.dumps(generate(args.experimental,args.ensemble_report,prospective=args.prospective),indent=2))
