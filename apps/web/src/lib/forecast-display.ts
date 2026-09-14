type Matchup = {
  id: number;
  team1_id: number | null;
  team2_id: number | null;
};

type ForecastSnapshot = {
  match_id: number;
  team1_id: number | null;
  team2_id: number | null;
  team1_win_probability: number;
  rationale: string | null;
};

type ForecastDisplay = {
  team1Probability: number | null;
  description: string;
};

/** Resolve a saved prediction against the current participants, by identity. */
export function getForecastDisplay(
  match: Matchup,
  forecast: ForecastSnapshot | null | undefined,
): ForecastDisplay {
  if (!forecast) {
    return {
      team1Probability: null,
      description: "No forecast recorded",
    };
  }

  if (
    match.team1_id == null ||
    match.team2_id == null ||
    forecast.team1_id == null ||
    forecast.team2_id == null ||
    match.team1_id === match.team2_id ||
    forecast.team1_id === forecast.team2_id
  ) {
    return {
      team1Probability: null,
      description: "Forecast unavailable: team identities are unresolved.",
    };
  }

  const sameOrder =
    match.team1_id === forecast.team1_id &&
    match.team2_id === forecast.team2_id;
  const reversedOrder =
    match.team1_id === forecast.team2_id &&
    match.team2_id === forecast.team1_id;

  if (match.id !== forecast.match_id || (!sameOrder && !reversedOrder)) {
    return {
      team1Probability: null,
      description: "Matchup changed. A new forecast is required.",
    };
  }

  const probability = forecast.team1_win_probability;
  if (!Number.isFinite(probability) || probability < 0 || probability > 1) {
    return {
      team1Probability: null,
      description: "Stored probability is unavailable.",
    };
  }

  return {
    team1Probability: reversedOrder ? 1 - probability : probability,
    // The stored rationale may describe ratings in the original team order.
    // Free text cannot safely be reoriented with the probability.
    description: reversedOrder
      ? "Forecast adjusted to the current team order."
      : (forecast.rationale ?? "Forecast available"),
  };
}
