from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.artifacts import canonical_json, digest, read_json, write_json
from app.research.evaluation import evaluate, metrics, replay
from app.research.online_models import EloState, fit_classifier
from app.research.elo import expected_score


START = datetime(2023,1,1,tzinfo=timezone.utc)


def dataset(count=150):
    rows = []
    for index in range(count):
        start = START + timedelta(days=index)
        rows.append({
            "id":index+1,"vlr_id":index+1,"team1_id":1,"team2_id":2,
            "status":"completed","team1_score":2 if index % 3 else 0,
            "team2_score":0 if index % 3 else 2,
            "scheduled_at":start.isoformat(),
            "schedule_observed_at":(start-timedelta(hours=1)).isoformat(),
            "result_observed_at":(start+timedelta(hours=2)).isoformat(),
            "event_name":"Synthetic test fixture","exclusion_reason":None,
        })
    return {"as_of":(START+timedelta(days=count+1)).isoformat(),"rows":rows,"result_events":rows}


def test_unknown_history_is_blocked_and_metrics_are_null():
    sample = dataset(4)
    for row in sample["rows"]:
        row["result_observed_at"] = None
    report = evaluate(sample,START,START+timedelta(days=1))
    assert report["status"] == "BLOCKED"
    assert report["exclusions"] == {"UNKNOWN_RESULT_AVAILABILITY":4}
    assert all(m["test"]["brier"] is None for m in report["models"].values())
    assert not report["ensemble"]["evidence_supports_review"]


def test_future_results_do_not_change_earlier_probabilities_or_features():
    original = dataset(150)
    modified = deepcopy(original)
    for row in modified["rows"][100:]:
        row["team1_score"],row["team2_score"] = row["team2_score"],row["team1_score"]
    a,_ = replay(original,minimum_training=20)
    b,_ = replay(modified,minimum_training=20)
    assert a[:100] == b[:100]
    assert "logistic_v1" in a[90]["probabilities"]
    assert "boosting_v1" in a[90]["probabilities"]


def test_delayed_results_and_equal_timestamps_cannot_update_early():
    sample = dataset(4)
    sample["rows"][0]["result_observed_at"] = sample["rows"][2]["scheduled_at"]
    records,_ = replay(sample)
    assert records[0]["probabilities"]["elo_v1"] == 0.5
    assert records[1]["probabilities"]["elo_v1"] == 0.5
    assert records[2]["probabilities"]["elo_v1"] == pytest.approx(expected_score(1516,1484))
    simultaneous = dataset(2)
    simultaneous["rows"][1]["scheduled_at"] = simultaneous["rows"][0]["scheduled_at"]
    simultaneous["rows"][1]["schedule_observed_at"] = simultaneous["rows"][0]["schedule_observed_at"]
    records,_ = replay(simultaneous)
    assert [r["probabilities"]["elo_v1"] for r in records] == [0.5,0.5]


def test_future_schedule_observation_excludes_target():
    sample = dataset(1)
    sample["rows"][0]["schedule_observed_at"] = sample["rows"][0]["scheduled_at"]
    records,reasons = replay(sample)
    assert records == []
    assert reasons == {"SCHEDULE_NOT_KNOWN_BEFORE_START":1}


def test_reproducible_across_input_order_and_repeated_runs():
    sample = dataset(80)
    one = evaluate(sample,START+timedelta(days=20),START+timedelta(days=50),minimum_training=10)
    sample["rows"].reverse()
    two = evaluate(sample,START+timedelta(days=20),START+timedelta(days=50),minimum_training=10)
    assert digest(canonical_json(one)) == digest(canonical_json(two))


def test_elo_v1_frozen_math_and_v2_half_life():
    frozen, decay = EloState(),EloState(90)
    for state in (frozen,decay):
        state.learn(1,2,1,START)
    later = START+timedelta(days=90)
    assert frozen.rating(1,later) == 1516
    assert decay.rating(1,later) == 1508
    assert frozen.predict(1,2,later) == expected_score(1516,1484)


def test_metrics_calibration_and_probability_quality():
    result = metrics([{"probability":0.8,"outcome":1},{"probability":0.8,"outcome":0}])
    assert result["accuracy"] == 0.5
    assert result["brier"] == pytest.approx(0.34)
    assert result["calibration"][8]["observed_win_rate"] == 0.5
    assert result["ece"] == pytest.approx(0.3)


def test_classifier_does_not_invent_training_labels():
    assert fit_classifier("logistic_v1",[[0]]*100,[1]*100) is None
    assert fit_classifier("boosting_v1",[[0]],[1]) is None


def test_artifact_reuse_and_corruption_detection(tmp_path,monkeypatch):
    import app.artifacts as artifacts
    monkeypatch.setattr(artifacts,"ARTIFACT_ROOT",tmp_path)
    key = write_json("datasets",{"value":1})
    assert write_json("datasets",{"value":1}) == key
    assert read_json("datasets",key) == {"value":1}
    artifacts.artifact_path("datasets",key).write_bytes(b"corrupt")
    with pytest.raises(ValueError,match="hash mismatch"):
        read_json("datasets",key)
    with pytest.raises(ValueError,match="integrity failure"):
        write_json("datasets",{"value":1})


def test_late_correction_cannot_rewrite_earlier_model_inputs():
    original = dataset(150)
    corrected = deepcopy(original)
    corrected["result_events"] = deepcopy(original["result_events"])
    changed = dict(corrected["result_events"][0])
    changed.update(team1_score=2,team2_score=0,result_observed_at=(START+timedelta(days=100,hours=1)).isoformat())
    corrected["result_events"].append(changed)
    left,_ = replay(original,minimum_training=20)
    right,_ = replay(corrected,minimum_training=20)
    assert left[:101] == right[:101]
    assert left[101]["features"] != right[101]["features"]


def test_repeated_observations_do_not_count_as_additional_results():
    original = dataset(3)
    repeated = deepcopy(original)
    repeated["result_events"] = list(repeated["result_events"]) + [dict(original["rows"][0],result_observed_at=(START+timedelta(hours=3)).isoformat())]
    assert replay(original)[0] == replay(repeated)[0]


def test_later_invalid_label_does_not_remove_a_past_training_example():
    original = dataset(150)
    corrected = deepcopy(original)
    corrected["result_events"] = deepcopy(original["result_events"])
    corrected["rows"][0]["exclusion_reason"] = "tied_score"
    corrected["rows"][0]["team1_score"] = corrected["rows"][0]["team2_score"] = 0
    corrected["result_events"].append(dict(corrected["rows"][0],result_observed_at=(START+timedelta(days=100,hours=1)).isoformat()))
    left,_ = replay(original,minimum_training=20)
    right,_ = replay(corrected,minimum_training=20)
    assert left[1:101] == right[:100]
