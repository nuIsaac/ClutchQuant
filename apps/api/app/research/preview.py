"""Current research previews. Never writes forecasts or claims availability."""
import argparse
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.models import Match, Team
from app.match_eligibility import match_exclusion_reason
from app.research.elo import DEFAULT_RATING, expected_score, update_ratings

HISTORY = Path(__file__).with_name("preview_history.json")
VERSION = "research:elo:v1:current-preview-v1"


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def current_rows(db):
    a, b = aliased(Team), aliased(Team)
    rows = db.execute(select(Match, a.vlr_id, b.vlr_id, match_exclusion_reason())
                      .join(a, a.id == Match.team1_id).join(b, b.id == Match.team2_id))
    # None is an explicit retraction/unknown, so cloud corrections do not leave
    # an eligible historical version silently active.
    return {m.vlr_id: [m.vlr_id, x, y, m.team1_score, m.team2_score,
                      m.scheduled_at.isoformat()] if reason is None and x and y and x != y else None
            for m, x, y, reason in rows if m.vlr_id is not None}


@lru_cache(maxsize=1)
def load_history():
    data = json.loads(HISTORY.read_text())
    if hashlib.sha256(encode(data["rows"])).hexdigest() != data["sha256"]:
        raise ValueError("Research history checksum mismatch")
    return data


def build_state(rows, now):
    ratings = {}
    used = []
    for row in sorted((r for r in rows if r is not None), key=lambda r: (r[5], r[0])):
        mid, a, b, sa, sb, at = row
        when = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if when.tzinfo is None or when >= now or a == b or min(sa, sb) < 0 or sa == sb:
            continue
        ratings[a], ratings[b] = update_ratings(ratings.get(a, DEFAULT_RATING),
                                               ratings.get(b, DEFAULT_RATING), int(sa > sb))
        used.append(row)
    return ratings, used


def previews(db, matches):
    try:
        history = load_history()
    except (OSError, ValueError, KeyError):
        return {}  # Missing preview is unknown, never a substituted 50%.
    merged = {r[0]: r for r in history["rows"]}
    merged.update(current_rows(db))
    now = datetime.now(timezone.utc)
    ratings, used = build_state(merged.values(), now)
    from collections import Counter
    counts = Counter(team for row in used for team in row[1:3])
    state_key = hashlib.sha256(encode(used)).hexdigest()
    ids = {m.team1_id for m in matches} | {m.team2_id for m in matches}
    teams = dict(db.execute(select(Team.id, Team.vlr_id).where(Team.id.in_(ids))).all())
    result = {}
    for m in matches:
        a, b = teams.get(m.team1_id), teams.get(m.team2_id)
        if not a or not b or a == b or not used:
            continue
        result[m.id] = dict(source_key=VERSION, team1_win_probability=expected_score(
            ratings.get(a, DEFAULT_RATING), ratings.get(b, DEFAULT_RATING)),
            computed_at=now, history_count=len(used), dataset_sha256=state_key,
            base_dataset_sha256=history["sha256"], base_exported_at=history["exported_at"],
            team1_unseen=a not in ratings, team2_unseen=b not in ratings,
            team1_rating=ratings.get(a, DEFAULT_RATING), team2_rating=ratings.get(b, DEFAULT_RATING),
            team1_history_count=counts[a], team2_history_count=counts[b],
            availability="UNKNOWN", used_for_prospective_scoring=False)
    return result


def main():
    parser = argparse.ArgumentParser(description="Export broad research history; no prospective writes")
    parser.add_argument("--export", action="store_true", required=True)
    parser.parse_args()
    from app.database import engine
    from sqlalchemy.orm import Session
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c:
        with c.begin():
            c.exec_driver_sql("SET TRANSACTION READ ONLY")
            with Session(bind=c) as db:
                _, rows = build_state(current_rows(db).values(), datetime.now(timezone.utc))
    if not rows:
        raise ValueError("Refusing an empty historical export")
    data = dict(protocol=VERSION, exported_at=datetime.now(timezone.utc).isoformat(),
                availability="UNKNOWN", sha256=hashlib.sha256(encode(rows)).hexdigest(), rows=rows)
    HISTORY.write_bytes(encode(data) + b"\n")
    print(json.dumps({"history_count": len(rows), "sha256": data["sha256"]}))


if __name__ == "__main__":
    main()
