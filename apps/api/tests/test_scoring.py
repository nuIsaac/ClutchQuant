import pytest

from app.scoring import (
    calculate_brier_score,
    calculate_log_loss,
    resolve_team1_outcome,
)


def test_resolves_team1_win():
    assert resolve_team1_outcome(2, 1) == 1


def test_resolves_team1_loss():
    assert resolve_team1_outcome(0, 2) == 0


def test_rejects_missing_or_tied_result():
    with pytest.raises(ValueError):
        resolve_team1_outcome(None, 2)

    with pytest.raises(ValueError):
        resolve_team1_outcome(1, 1)


def test_calculates_brier_score():
    assert calculate_brier_score(
        0.70,
        1,
    ) == pytest.approx(0.09)

    assert calculate_brier_score(
        0.70,
        0,
    ) == pytest.approx(0.49)


def test_calculates_log_loss():
    assert calculate_log_loss(
        0.70,
        1,
    ) == pytest.approx(0.35667494)


def test_rejects_invalid_scoring_inputs():
    with pytest.raises(ValueError):
        calculate_brier_score(1.2, 1)

    with pytest.raises(ValueError):
        calculate_log_loss(0.5, 3)