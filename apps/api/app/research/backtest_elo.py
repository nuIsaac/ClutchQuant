from sqlalchemy import select

from app.database import SessionLocal
from app.models import Match
from app.scoring import (
    calculate_brier_score,
    calculate_log_loss,
    resolve_team1_outcome,
)
from app.research.elo import (
    get_team_rating,
    predict_match,
    update_ratings,
)


def run_elo_backtest() -> None:
    ratings: dict[int, float] = {}

    predictions = 0
    correct = 0
    total_brier = 0.0
    total_log_loss = 0.0

    with SessionLocal() as db:
        matches = db.scalars(
            select(Match)
            .where(
                Match.team1_score.is_not(None),
                Match.team2_score.is_not(None),
                Match.team1_score != Match.team2_score,
                Match.scheduled_at.is_not(None),
            )
            .order_by(Match.scheduled_at.asc())
        ).all()

        for match in matches:
            # IMPORTANT:
            # Predict BEFORE using this match's result.
            probability = predict_match(
                ratings,
                match.team1_id,
                match.team2_id,
            )

            outcome = resolve_team1_outcome(
                match.team1_score,
                match.team2_score,
            )

            predicted_winner = 1 if probability >= 0.5 else 0

            if predicted_winner == outcome:
                correct += 1

            total_brier += calculate_brier_score(
                probability,
                outcome,
            )

            total_log_loss += calculate_log_loss(
                probability,
                outcome,
            )

            predictions += 1

            # Only now do we let Elo learn the result.
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

    if predictions == 0:
        print("No completed matches found.")
        return

    accuracy = correct / predictions
    average_brier = total_brier / predictions
    average_log_loss = total_log_loss / predictions

    print(f"Matches evaluated: {predictions}")
    print(f"Accuracy: {accuracy:.3f}")
    print(f"Brier score: {average_brier:.3f}")
    print(f"Log loss: {average_log_loss:.3f}")
    print(f"Teams rated: {len(ratings)}")


if __name__ == "__main__":
    run_elo_backtest()