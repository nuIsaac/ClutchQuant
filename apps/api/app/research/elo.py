DEFAULT_RATING = 1500.0
K_FACTOR = 32.0


def expected_score(
    rating_a: float,
    rating_b: float,
) -> float:
    """
    Return the expected probability that team A beats team B.
    """

    return 1.0 / (
        1.0 + 10 ** ((rating_b - rating_a) / 400.0)
    )


def update_ratings(
    rating_a: float,
    rating_b: float,
    outcome_a: int,
    k_factor: float = K_FACTOR,
) -> tuple[float, float]:
    """
    Update both Elo ratings after a completed match.

    outcome_a:
        1 -> team A won
        0 -> team A lost
    """

    if outcome_a not in (0, 1):
        raise ValueError("outcome_a must be either 0 or 1.")

    expected_a = expected_score(
        rating_a,
        rating_b,
    )

    expected_b = 1.0 - expected_a
    outcome_b = 1 - outcome_a

    new_rating_a = rating_a + (
        k_factor * (outcome_a - expected_a)
    )

    new_rating_b = rating_b + (
        k_factor * (outcome_b - expected_b)
    )

    return new_rating_a, new_rating_b


def get_team_rating(
    ratings: dict[int, float],
    team_id: int,
) -> float:
    """
    Return a team's current rating.
    New teams start at the default rating.
    """

    return ratings.get(
        team_id,
        DEFAULT_RATING,
    )


def predict_match(
    ratings: dict[int, float],
    team1_id: int,
    team2_id: int,
) -> float:
    """
    Return team 1's win probability.
    """

    team1_rating = get_team_rating(
        ratings,
        team1_id,
    )

    team2_rating = get_team_rating(
        ratings,
        team2_id,
    )

    return expected_score(
        team1_rating,
        team2_rating,
    )