from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Forecast, Match
from app.research.elo import (
    get_team_rating,
    predict_match,
    update_ratings,
)
from app.scoring import resolve_team1_outcome


SOURCE_KEY = "model:elo:v1"


def generate_elo_forecasts() -> None:
    ratings: dict[int, float] = {}

    created = 0
    skipped = 0

    with SessionLocal() as db:
        completed_matches = db.scalars(
            select(Match)
            .where(
                Match.status == "completed",
                Match.team1_score.is_not(None),
                Match.team2_score.is_not(None),
                Match.team1_score != Match.team2_score,
                Match.scheduled_at.is_not(None),
            )
            .order_by(Match.scheduled_at.asc())
        ).all()

        # Build current ratings using only completed historical matches.
        for match in completed_matches:
            outcome = resolve_team1_outcome(
                match.team1_score,
                match.team2_score,
            )

            team1_rating = get_team_rating(
                ratings,
                match.team1_id,
            )

            team2_rating = get_team_rating(
                ratings,
                match.team2_id,
            )

            new_team1_rating, new_team2_rating = update_ratings(
                team1_rating,
                team2_rating,
                outcome,
            )

            ratings[match.team1_id] = new_team1_rating
            ratings[match.team2_id] = new_team2_rating

        now = datetime.now(timezone.utc)

        upcoming_matches = db.scalars(
            select(Match)
            .where(
                Match.status == "scheduled",
                Match.scheduled_at.is_not(None),
                Match.scheduled_at > now,
            )
            .order_by(Match.scheduled_at.asc())
        ).all()

        for match in upcoming_matches:
            existing = db.scalar(
                select(Forecast).where(
                    Forecast.match_id == match.id,
                    Forecast.source_key == SOURCE_KEY,
                )
            )

            if existing is not None:
                skipped += 1
                continue

            probability = predict_match(
                ratings,
                match.team1_id,
                match.team2_id,
            )

            team1_rating = get_team_rating(
                ratings,
                match.team1_id,
            )

            team2_rating = get_team_rating(
                ratings,
                match.team2_id,
            )

            forecast = Forecast(
                match_id=match.id,
                team1_id=match.team1_id,
                team2_id=match.team2_id,
                source_type="model",
                source_key=SOURCE_KEY,
                team1_win_probability=probability,
                rationale=(
                    f"Elo v1 ratings: "
                    f"{team1_rating:.1f} vs {team2_rating:.1f}"
                ),
                lock_time=match.scheduled_at,
            )

            db.add(forecast)
            created += 1

        db.commit()

    print(f"Forecasts created: {created}")
    print(f"Existing forecasts skipped: {skipped}")
    print(f"Teams rated: {len(ratings)}")


if __name__ == "__main__":
    generate_elo_forecasts()