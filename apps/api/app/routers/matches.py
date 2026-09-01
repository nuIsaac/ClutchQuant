from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, aliased

from app.dependencies import get_db
from app.models import Match, Team
from app.schemas import UpcomingMatchResponse


router = APIRouter(
    prefix="/api/v1/matches",
    tags=["matches"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


@router.get(
    "/upcoming",
    response_model=list[UpcomingMatchResponse],
)
def list_upcoming_matches(
    db: DatabaseSession,
) -> list[UpcomingMatchResponse]:
    now = datetime.now(timezone.utc)

    team1 = aliased(Team)
    team2 = aliased(Team)

    rows = (
        db.query(
            Match,
            team1.name.label("team1_name"),
            team2.name.label("team2_name"),
        )
        .join(
            team1,
            team1.id == Match.team1_id,
        )
        .join(
            team2,
            team2.id == Match.team2_id,
        )
        .filter(
            Match.status == "scheduled",
            Match.scheduled_at.is_not(None),
            Match.scheduled_at > now,
        )
        .order_by(Match.scheduled_at.asc())
        .all()
    )

    return [
        UpcomingMatchResponse(
            id=match.id,
            vlr_id=match.vlr_id,
            team1_id=match.team1_id,
            team1_name=team1_name,
            team2_id=match.team2_id,
            team2_name=team2_name,
            event_name=match.event_name,
            stage=match.stage,
            status=match.status,
            scheduled_at=match.scheduled_at,
        )
        for match, team1_name, team2_name in rows
    ]