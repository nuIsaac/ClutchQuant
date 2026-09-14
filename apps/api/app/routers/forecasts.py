from datetime import datetime, timezone
import secrets
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Header,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased

from app.dependencies import get_db
from app import settings
from app.match_eligibility import match_exclusion_reason
from app.models import Forecast, Match, Team
from app.schemas import (
    ForecastCreate,
    ForecastResponse,
    ForecastScoreResponse,
)
from app.scoring import (
    calculate_brier_score,
    calculate_log_loss,
    resolve_team1_outcome,
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
    authorization: str | None = Header(default=None),
) -> Forecast:
    # Public deployments are read-only unless the operator configures a token.
    # This is an operator gate, not a multi-user identity system.
    if settings.APP_ENV != "development":
        if not settings.HUMAN_FORECAST_TOKEN:
            raise HTTPException(status_code=403,detail="Forecast submission is disabled.")
        expected = f"Bearer {settings.HUMAN_FORECAST_TOKEN}"
        if not authorization or not secrets.compare_digest(authorization,expected):
            raise HTTPException(status_code=401,detail="Valid operator authorization required.")
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
        or match.team1_id == match.team2_id
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
        created_at=now,
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
                "The forecast conflicts with an existing forecast "
                "or a database integrity constraint."
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
    source_key: str | None = Query(default=None,max_length=150),
    limit: int = Query(default=200,ge=1,le=500),
    offset: int = Query(default=0,ge=0),
) -> list[Forecast]:
    query = db.query(Forecast)

    if match_id is not None:
        query = query.filter(
            Forecast.match_id == match_id
        )
    if source_key is not None:
        query = query.filter(Forecast.source_key == source_key)

    return (
        query
        .order_by(Forecast.created_at.desc())
        .offset(offset).limit(limit)
        .all()
    )

@router.get(
    "/scores",
    response_model=list[ForecastScoreResponse],
)
def list_scored_forecasts(
    db: DatabaseSession,
    match_id: int | None = Query(
        default=None,
        gt=0,
    ),
    source_key: str | None = Query(
        default=None,
        min_length=1,
        max_length=150,
    ),
    limit: int = Query(default=200,ge=1,le=500),
    offset: int = Query(default=0,ge=0),
) -> list[ForecastScoreResponse]:
    team1 = aliased(Team)
    team2 = aliased(Team)

    query = (
        db.query(
            Forecast,
            Match,
            team1.name.label("team1_name"),
            team2.name.label("team2_name"),
        )
        .join(
            Match,
            Match.id == Forecast.match_id,
        )
        .join(
            team1,
            team1.id == Forecast.team1_id,
        )
        .join(
            team2,
            team2.id == Forecast.team2_id,
        )
        .filter(
            match_exclusion_reason().is_(None),
            or_(
                and_(Forecast.team1_id == Match.team1_id, Forecast.team2_id == Match.team2_id),
                and_(Forecast.team1_id == Match.team2_id, Forecast.team2_id == Match.team1_id),
            ),
        )
    )

    if match_id is not None:
        query = query.filter(
            Forecast.match_id == match_id
        )

    if source_key is not None:
        query = query.filter(
            Forecast.source_key == source_key
        )

    rows = (
        query
        .order_by(Forecast.created_at.desc())
        .offset(offset).limit(limit)
        .all()
    )

    responses = []

    for (
        forecast,
        match,
        team1_name,
        team2_name,
    ) in rows:
        # Scores and probabilities in this response always follow the
        # forecast snapshot, even if ingestion later reverses team order.
        if (forecast.team1_id, forecast.team2_id) == (match.team1_id, match.team2_id):
            team1_score, team2_score = match.team1_score, match.team2_score
        elif (forecast.team1_id, forecast.team2_id) == (match.team2_id, match.team1_id):
            team1_score, team2_score = match.team2_score, match.team1_score
        else:
            # A replacement opponent makes this a different prediction task.
            # Keep the forecast in storage and the unscored listing.
            continue

        outcome = resolve_team1_outcome(
            team1_score,
            team2_score,
        )

        responses.append(
            ForecastScoreResponse(
                forecast_id=forecast.id,
                match_id=forecast.match_id,
                source_type=forecast.source_type,
                source_key=forecast.source_key,
                team1_id=forecast.team1_id,
                team1_name=team1_name,
                team2_id=forecast.team2_id,
                team2_name=team2_name,
                team1_win_probability=(
                    forecast.team1_win_probability
                ),
                team1_score=team1_score,
                team2_score=team2_score,
                team1_outcome=outcome,
                brier_score=calculate_brier_score(
                    forecast.team1_win_probability,
                    outcome,
                ),
                log_loss=calculate_log_loss(
                    forecast.team1_win_probability,
                    outcome,
                ),
            )
        )

    return responses
