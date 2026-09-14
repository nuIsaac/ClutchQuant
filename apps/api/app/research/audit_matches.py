"""Print eligibility counts and excluded record IDs without changing data."""

import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.match_eligibility import (
    ELIGIBILITY_POLICY_VERSION,
    match_exclusion_reason,
)
from app.models import Match


def audit_matches(db: Session) -> dict:
    counts: Counter[str] = Counter()
    excluded = []
    for match_id, vlr_id, reason in db.execute(
        select(Match.id, Match.vlr_id, match_exclusion_reason())
        .order_by(Match.id)
    ):
        counts[reason or "eligible"] += 1
        if reason is not None:
            excluded.append({
                "match_id": match_id,
                "vlr_id": vlr_id,
                "reason": reason,
            })
    return {
        "eligibility_policy": ELIGIBILITY_POLICY_VERSION,
        "counts": dict(sorted(counts.items())),
        "excluded_matches": excluded,
    }


if __name__ == "__main__":
    with SessionLocal() as session:
        print(json.dumps(audit_matches(session), indent=2))
