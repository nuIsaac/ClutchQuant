"""Small, versioned model implementations; Elo v1 math is imported unchanged."""

from collections import defaultdict
from datetime import datetime
import math
from threadpoolctl import threadpool_limits

from app.research.elo import DEFAULT_RATING, K_FACTOR, expected_score, update_ratings


FEATURE_VERSION = "observed-form-v1"
FEATURE_NAMES = (
    "elo_probability", "recent_win_rate_difference", "recent_count_difference",
    "days_since_observed_match_difference", "opponent_rating_difference",
    "team1_history_missing", "team2_history_missing",
)
CONFIGS = {
    "elo_v1": {"source_key": "model:elo:v1:observed-v1", "family": "elo", "half_life_days": None},
    **{f"elo_v2_{days}": {
        "source_key": f"model:elo:v2:decay{days}:observed-v1",
        "family": "elo", "half_life_days": days,
    } for days in (30, 90, 180)},
    "logistic_v1": {"source_key": "model:logistic:v1:observed-v1", "family": "logistic", "C": 1.0,
                    "refit_cutoff":"UTC month start","minimum_training":100},
    "boosting_v1": {"source_key": "model:boosting:v1:observed-v1", "family": "boosting",
                    "max_iter": 100, "max_leaf_nodes": 7, "learning_rate": 0.05,
                    "refit_cutoff":"UTC month start","minimum_training":100},
}
ENSEMBLE_COMPONENTS = ("elo_v1", "elo_v2_90", "logistic_v1", "boosting_v1")


class EloState:
    def __init__(self, half_life_days=None):
        if half_life_days is not None and half_life_days <= 0:
            raise ValueError("Half-life must be positive")
        self.half_life_days = half_life_days
        self.ratings = {}
        self.updated_at = {}

    def rating(self, team: int, at: datetime) -> float:
        value = self.ratings.get(team, DEFAULT_RATING)
        if self.half_life_days and team in self.updated_at:
            days = (at - self.updated_at[team]).total_seconds() / 86400
            if days < 0:
                raise ValueError("Cannot read rating state before its last update")
            value = DEFAULT_RATING + (value - DEFAULT_RATING) * 2 ** (-days / self.half_life_days)
        return value

    def predict(self, team1, team2, at):
        return expected_score(self.rating(team1, at), self.rating(team2, at))

    def learn(self, team1, team2, outcome, at):
        first, second = update_ratings(self.rating(team1, at), self.rating(team2, at), outcome)
        self.ratings[team1], self.ratings[team2] = first, second
        self.updated_at[team1] = self.updated_at[team2] = at


class FormState:
    """Only observations released by the replay clock enter these histories."""
    def __init__(self):
        self.histories = defaultdict(list)

    def learn(self, team1, team2, outcome, event_at, opponent1, opponent2):
        self.histories[team1].append((event_at, outcome, opponent1))
        self.histories[team2].append((event_at, 1 - outcome, opponent2))

    def summary(self, team, at):
        history = self.histories[team]
        if not history:
            return (0.5, 0, 0.0, DEFAULT_RATING, 1)
        recent = [item for item in history if 0 <= (at - item[0]).total_seconds() < 90 * 86400]
        elapsed = max(0.0, (at - max(item[0] for item in history)).total_seconds() / 86400)
        return (
            sum(item[1] for item in recent) / len(recent) if recent else 0.5,
            len(recent), elapsed,
            sum(item[2] for item in recent) / len(recent) if recent else DEFAULT_RATING,
            int(not recent),
        )

    def features(self, team1, team2, at, elo):
        a, b = self.summary(team1, at), self.summary(team2, at)
        return [elo.predict(team1, team2, at), a[0]-b[0], math.log1p(a[1])-math.log1p(b[1]),
                math.log1p(a[2])-math.log1p(b[2]), (a[3]-b[3])/400, a[4], b[4]]


def fit_classifier(name, features, outcomes, minimum=100):
    if len(outcomes) < minimum or len(set(outcomes)) < 2:
        return None
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if name == "logistic_v1":
        estimator = make_pipeline(StandardScaler(), LogisticRegression(
            C=CONFIGS[name]["C"], max_iter=1000, random_state=0))
    elif name == "boosting_v1":
        cfg = CONFIGS[name]
        estimator = HistGradientBoostingClassifier(
            max_iter=cfg["max_iter"], max_leaf_nodes=cfg["max_leaf_nodes"],
            learning_rate=cfg["learning_rate"], random_state=0, early_stopping=False)
    else:
        raise ValueError("Unknown classifier")
    with threadpool_limits(limits=1):
        return estimator.fit(features, outcomes)


def classifier_probability(estimator, features):
    with threadpool_limits(limits=1):
        return float(estimator.predict_proba([features])[0][1])
