"""Dataset eligibility, separate from raw ingestion and Elo parameters.

The first applicable reason wins. Unknown values remain unknown in storage.
This policy does not establish when a historical result became available.
"""

from sqlalchemy import Select, case, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.models import Match


ELIGIBILITY_POLICY_VERSION = "decisive-v1"


def match_exclusion_reason(entity=Match) -> ColumnElement[str]:
    """Return a SQL expression yielding NULL for eligible series."""
    return case(
        (
            or_(entity.status.is_(None), entity.status != "completed"),
            "not_completed",
        ),
        (
            or_(entity.team1_score.is_(None), entity.team2_score.is_(None)),
            "missing_score",
        ),
        (
            or_(entity.team1_score < 0, entity.team2_score < 0),
            "negative_score",
        ),
        (entity.team1_score == entity.team2_score, "tied_score"),
        (entity.team1_id == entity.team2_id, "same_team"),
        (entity.scheduled_at.is_(None), "missing_start_time"),
        else_=None,
    )


def eligible_matches_query() -> Select[tuple[Match]]:
    return (
        select(Match)
        .where(match_exclusion_reason().is_(None))
        .order_by(Match.scheduled_at.asc(), Match.id.asc())
    )
