"""Deterministic observation-time replay, with no fabricated availability."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from app.research.dataset import utc
from app.research.online_models import CONFIGS, ENSEMBLE_COMPONENTS, EloState, FormState, fit_classifier, classifier_probability
from app.scoring import calculate_brier_score, calculate_log_loss


def metrics(records):
    if not records:
        return {"count": 0, "accuracy": None, "brier": None, "log_loss": None,
                "calibration": [], "ece": None}
    bins = []
    for index in range(10):
        values = [r for r in records if min(int(r["probability"] * 10), 9) == index]
        bins.append({"lower": index/10, "upper": (index+1)/10, "count": len(values),
                     "mean_probability": sum(r["probability"] for r in values)/len(values) if values else None,
                     "observed_win_rate": sum(r["outcome"] for r in values)/len(values) if values else None})
    count = len(records)
    return {
        "count": count,
        "accuracy": sum((r["probability"] >= 0.5) == r["outcome"] for r in records)/count,
        "brier": sum(calculate_brier_score(r["probability"],r["outcome"]) for r in records)/count,
        "log_loss": sum(calculate_log_loss(r["probability"],r["outcome"]) for r in records)/count,
        "calibration": bins,
        "ece": sum(b["count"] * abs(b["mean_probability"]-b["observed_win_rate"])
                   for b in bins if b["count"])/count,
    }


def legacy_diagnostic(dataset):
    """Reproduce the old benchmark, explicitly NOT availability-safe evidence."""
    from app.research.elo import predict_match, get_team_rating, update_ratings
    ratings,records = {},[]
    rows = sorted((r for r in dataset["rows"] if r["exclusion_reason"] is None),
                  key=lambda r:(utc(r["scheduled_at"]),r["id"]))
    for row in rows:
        a,b = row["team1_id"],row["team2_id"]
        outcome = int(row["team1_score"] > row["team2_score"])
        records.append({"probability":predict_match(ratings,a,b),"outcome":outcome})
        ratings[a],ratings[b] = update_ratings(get_team_rating(ratings,a),get_team_rating(ratings,b),outcome)
    return {"status":"DIAGNOSTIC_ONLY_NOT_LEAKAGE_SAFE","metrics":metrics(records),
            "teams_rated":len(ratings),"reason":"Scheduled-order replay does not establish historical result availability"}


def history_rows(dataset, cutoff):
    released = {}
    events = sorted((r for r in dataset.get("result_events",[]) if r.get("result_observed_at")),
                    key=lambda r:(utc(r["result_observed_at"]),r.get("observation_id",r["id"])))
    for event in events:
        if utc(event["result_observed_at"]) < cutoff:
            if event["exclusion_reason"] is None and utc(event["scheduled_at"]) < utc(event["result_observed_at"]):
                previous = released.get(event["id"])
                if previous is None or result_identity(previous) != result_identity(event):
                    released[event["id"]] = event
            else:
                released.pop(event["id"],None)
    return sorted(released.values(),key=lambda r:(utc(r["result_observed_at"]),r["id"]))


def result_identity(row):
    return tuple(row.get(key) for key in ("team1_id","team2_id","team1_score","team2_score","scheduled_at"))


def learning_states(events):
    states = {name:EloState(cfg["half_life_days"]) for name,cfg in CONFIGS.items() if cfg["family"] == "elo"}
    form = FormState()
    for event in events:
        learn_event(states,form,event)
    return states,form


def learn_event(states,form,event):
    available = utc(event["result_observed_at"])
    a,b = event["team1_id"],event["team2_id"]
    outcome = int(event["team1_score"] > event["team2_score"])
    form.learn(a,b,outcome,utc(event["scheduled_at"]),states["elo_v1"].rating(b,available),states["elo_v1"].rating(a,available))
    for state in states.values():
        state.learn(a,b,outcome,available)


def replay(dataset, *, minimum_training=100, include_unscored=False, fit_models=True):
    as_of = utc(dataset["as_of"])
    exclusions = Counter()
    targets = []
    for row in dataset["rows"]:
        prediction = row.get("prediction",row)
        target = dict(row)
        if prediction:
            target.update(prediction)
        if prediction and (target["team1_id"],target["team2_id"]) == (row["team2_id"],row["team1_id"]):
            target["team1_score"],target["team2_score"] = row["team2_score"],row["team1_score"]
        reason = row["exclusion_reason"]
        if reason is None:
            if not row.get("result_observed_at"):
                reason = "UNKNOWN_RESULT_AVAILABILITY"
            elif utc(row["result_observed_at"]) > as_of:
                reason = "RESULT_AFTER_AS_OF"
            elif not prediction or not target.get("schedule_observed_at"):
                reason = "UNKNOWN_PREMATCH_SCHEDULE"
            elif utc(target["schedule_observed_at"]) >= utc(target["scheduled_at"]):
                reason = "SCHEDULE_NOT_KNOWN_BEFORE_START"
            elif {target["team1_id"],target["team2_id"]} != {row["team1_id"],row["team2_id"]}:
                reason = "MATCHUP_CHANGED"
            elif utc(row["result_observed_at"]) <= utc(target["scheduled_at"]):
                reason = "RESULT_NOT_AFTER_START"
        if reason:
            exclusions[reason] += 1
        # Prediction inputs are built even for currently unresolved/ineligible
        # labels. Future corrections must not remove past training examples.
        if (prediction and target.get("schedule_observed_at") and target.get("scheduled_at")
                and utc(target["schedule_observed_at"]) < utc(target["scheduled_at"]) <= as_of):
            target["score_exclusion"] = reason
            targets.append(target)
    targets.sort(key=lambda row: (utc(row["scheduled_at"]),row["id"]))
    events = sorted((r for r in dataset.get("result_events",[]) if r.get("result_observed_at")),
                    key=lambda r:(utc(r["result_observed_at"]),r.get("observation_id",r["id"])))
    event_index,known = 0,{}
    states,form = learning_states([])
    examples, records = [], []
    classifiers = {"logistic_v1":None,"boosting_v1":None}
    fit_month = None
    for row in targets:
        at = utc(row["scheduled_at"])
        rebuild = False
        while event_index < len(events) and utc(events[event_index]["result_observed_at"]) < at:
            event = events[event_index]
            event_index += 1
            previous = known.get(event["id"])
            valid = event["exclusion_reason"] is None and utc(event["scheduled_at"]) < utc(event["result_observed_at"])
            if not valid:
                if previous is not None:
                    del known[event["id"]]
                    rebuild = True
            elif previous is None:
                known[event["id"]] = event
                if not rebuild:
                    learn_event(states,form,event)
            elif result_identity(previous) != result_identity(event):
                known[event["id"]] = event
                rebuild = True
        if rebuild:
            # Corrections invalidate only the current state, never previously
            # emitted features. Repeated unchanged observations are ignored.
            states,form = learning_states(sorted(known.values(),key=lambda r:(utc(r["result_observed_at"]),r["id"])))
        features = form.features(row["team1_id"],row["team2_id"],at,states["elo_v1"])
        month = at.strftime("%Y-%m")
        if fit_models and month != fit_month:
            fit_cutoff = at.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
            fit_known = {event["id"]:event for event in history_rows(dataset,fit_cutoff)}
            training = []
            for example in examples:
                event = fit_known.get(example["match_id"])
                if event is not None and (event["team1_id"],event["team2_id"]) == example["teams"]:
                    training.append({"features":example["features"],
                                     "outcome":int(event["team1_score"] > event["team2_score"])})
            for name in classifiers:
                classifiers[name] = fit_classifier(name,[e["features"] for e in training],
                                                   [e["outcome"] for e in training],minimum_training)
            fit_month = month
        probabilities = {name:state.predict(row["team1_id"],row["team2_id"],at) for name,state in states.items()}
        for name, estimator in classifiers.items():
            if estimator is not None:
                probabilities[name] = classifier_probability(estimator,features)
        if all(name in probabilities for name in ENSEMBLE_COMPONENTS):
            probabilities["ensemble_v1"] = sum(probabilities[name] for name in ENSEMBLE_COMPONENTS)/len(ENSEMBLE_COMPONENTS)
        if row["score_exclusion"] is None or include_unscored:
            outcome = int(row["team1_score"] > row["team2_score"]) if row["score_exclusion"] is None else None
            records.append({"match_id":row["id"],"prediction_at":at.isoformat(),
                            "team1_id":row["team1_id"],"team2_id":row["team2_id"],
                            "result_available_at":row["result_observed_at"],"outcome":outcome,
                            "event_name":row.get("event_name"),"features":features,"probabilities":probabilities})
        examples.append({"features":features,"match_id":row["id"],"teams":(row["team1_id"],row["team2_id"])})
    return records, dict(sorted(exclusions.items()))


def evaluate(dataset, validation_start, test_start, *, minimum_training=100):
    validation_start, test_start = utc(validation_start), utc(test_start)
    as_of = utc(dataset["as_of"])
    if not validation_start < test_start < as_of:
        raise ValueError("Require validation_start < test_start < dataset as_of")
    records, exclusions = replay(dataset, minimum_training=minimum_training)
    model_names = list(CONFIGS) + ["ensemble_v1"]

    def summarize(selected, model):
        return metrics([{"probability":r["probabilities"][model],"outcome":r["outcome"]}
                        for r in selected if model in r["probabilities"]])

    validation = [r for r in records if validation_start <= utc(r["prediction_at"]) < test_start
                  and utc(r["result_available_at"]) < test_start]
    test = [r for r in records if utc(r["prediction_at"]) >= test_start]
    common_validation = [r for r in validation if all(m in r["probabilities"] for m in model_names)]
    common_test = [r for r in test if all(m in r["probabilities"] for m in model_names)]
    comparisons = {}
    for name in model_names:
        months = sorted({r["prediction_at"][:7] for r in test})
        comparisons[name] = {
            "all":summarize(records,name), "validation":summarize(validation,name),
            "test":summarize(test,name),
            "common_validation":summarize(common_validation,name),
            "common_test":summarize(common_test,name),
            "recent_90_days":summarize([r for r in test if utc(r["prediction_at"]) >= as_of-timedelta(days=90)],name),
            "by_month":{month:summarize([r for r in test if r["prediction_at"][:7] == month],name) for month in months},
            "by_event":{event:summarize([r for r in test if (r["event_name"] or "UNKNOWN") == event],name)
                        for event in sorted({r["event_name"] or "UNKNOWN" for r in test})},
        }
    candidate = None
    if len(common_validation) >= 100:
        candidate = min((n for n in CONFIGS if n.startswith("elo_v2")),
                        key=lambda n:(comparisons[n]["common_validation"]["brier"],comparisons[n]["common_validation"]["log_loss"]))
    # No automatic promotion from a single experiment. Fixed ensemble is
    # evaluated prospectively; evidence may justify a human review, not a claim.
    ensemble_support = False
    if len(common_validation) >= 100 and len(common_test) >= 200:
        ensemble_support = all(
            comparisons["ensemble_v1"][split][metric] < comparisons["elo_v1"][split][metric]
            for split in ("common_validation","common_test") for metric in ("brier","log_loss")
        )
    return {
        "status":"EVALUATED" if records else "BLOCKED",
        "blocker":None if records else "No eligible matches with both pre-match schedule and result-availability evidence",
        "validation_start":validation_start.isoformat(),"test_start":test_start.isoformat(),
        "minimum_training":minimum_training,"exclusions":exclusions,
        "configurations":CONFIGS,"feature_version":"observed-form-v1",
        "models":comparisons,"predictions":records,
        "selected_elo_v2_on_validation":candidate,
        "ensemble":{"components":list(ENSEMBLE_COMPONENTS),"weights":"equal",
                    "evidence_supports_review":ensemble_support,"promotion":"NOT_PROMOTED"},
        "unsupported_features":{
            "maps":"No time-safe historical feature snapshots",
            "roster_continuity":"No roster validity intervals",
            "region_and_tier":"No verified historical taxonomy",
            "head_to_head":"Not included without sufficient evidence of predictive value",
        },
    }
