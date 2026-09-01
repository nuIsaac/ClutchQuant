import math


def resolve_team1_outcome(
    team1_score: int | None,
    team2_score: int | None,
) -> int:
    if team1_score is None or team2_score is None:
        raise ValueError(
            "Both match scores are required."
        )

    if team1_score == team2_score:
        raise ValueError(
            "A completed Valorant match cannot be tied."
        )

    return int(team1_score > team2_score)


def calculate_brier_score(
    probability: float,
    outcome: int,
) -> float:
    validate_probability_and_outcome(
        probability,
        outcome,
    )

    return (probability - outcome) ** 2


def calculate_log_loss(
    probability: float,
    outcome: int,
) -> float:
    validate_probability_and_outcome(
        probability,
        outcome,
    )

    epsilon = 1e-15

    clipped_probability = min(
        max(probability, epsilon),
        1.0 - epsilon,
    )

    return -(
        outcome * math.log(clipped_probability)
        + (1 - outcome)
        * math.log(1.0 - clipped_probability)
    )


def validate_probability_and_outcome(
    probability: float,
    outcome: int,
) -> None:
    if not 0.0 <= probability <= 1.0:
        raise ValueError(
            "Probability must be between 0 and 1."
        )

    if outcome not in (0, 1):
        raise ValueError(
            "Outcome must be either 0 or 1."
        )