from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Forecast, Match
from app.schemas import (
    ForecastCreate,
    ForecastResponse,
)


router = APIRouter(
    prefix="/api/v1/forecasts",
    tags=["forecasts"],
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


@router.post(
    "",
    response_model=ForecastResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_forecast(
    payload: ForecastCreate,
    db: DatabaseSession,
) -> Forecast:
    match = db.get(
        Match,
        payload.match_id,
    )

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    if (
        match.status != "scheduled"
        or match.scheduled_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This match is not open "
                "for forecasting."
            ),
        )

    lock_time = match.scheduled_at

    if lock_time.tzinfo is None:
        lock_time = lock_time.replace(
            tzinfo=timezone.utc
        )

    now = datetime.now(timezone.utc)

    if now >= lock_time:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The forecast deadline "
                "has passed."
            ),
        )

    forecast = Forecast(
        match_id=match.id,
        team1_id=match.team1_id,
        team2_id=match.team2_id,
        source_type=payload.source_type,
        source_key=payload.source_key,
        team1_win_probability=(
            payload.team1_win_probability
        ),
        rationale=payload.rationale,
        lock_time=lock_time,
    )

    db.add(forecast)

    try:
        db.commit()

    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A forecast from this source "
                "already exists for this match."
            ),
        ) from error

    db.refresh(forecast)

    return forecast


@router.get(
    "",
    response_model=list[ForecastResponse],
)
def list_forecasts(
    db: DatabaseSession,
    match_id: int | None = Query(
        default=None,
        gt=0,
    ),
) -> list[Forecast]:
    query = db.query(Forecast)

    if match_id is not None:
        query = query.filter(
            Forecast.match_id == match_id
        )

    return (
        query
        .order_by(Forecast.created_at.desc())
        .all()
    )