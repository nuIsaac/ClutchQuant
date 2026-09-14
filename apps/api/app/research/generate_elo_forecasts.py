from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.match_eligibility import eligible_matches_query
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
    training_cutoff = datetime.now(timezone.utc)

    with SessionLocal() as db:
        completed_matches = db.scalars(
            eligible_matches_query().where(Match.scheduled_at < training_cutoff)
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
                Match.team1_id != Match.team2_id,
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

            # Lookups and computation can cross a deadline. Timestamp the
            # completed prediction, not the start of the loop/transaction.
            forecast_time = datetime.now(timezone.utc)
            lock_time = match.scheduled_at
            if lock_time.tzinfo is None:
                lock_time = lock_time.replace(tzinfo=timezone.utc)
            if forecast_time >= lock_time:
                skipped += 1
                continue

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
                created_at=forecast_time,
                lock_time=lock_time,
            )

            db.add(forecast)
            created += 1

        db.commit()

    print(f"Forecasts created: {created}")
    print(f"Forecasts skipped (existing or past deadline): {skipped}")
    print(f"Teams rated: {len(ratings)}")


if __name__ == "__main__":
    generate_elo_forecasts()
