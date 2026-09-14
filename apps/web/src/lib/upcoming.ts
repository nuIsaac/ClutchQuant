export type Forecast = {
  id: number;
  match_id: number;
  team1_id: number;
  team2_id: number;
  source_type: string;
  source_key: string;
  team1_win_probability: number;
  rationale: string | null;
  created_at: string;
  lock_time: string;
  model_run_id: string | null;
};

export type UpcomingMatch = {
  id: number;
  vlr_id: number | null;
  team1_id: number;
  team2_id: number;
  team1_name: string;
  team2_name: string;
  event_name: string | null;
  stage: string | null;
  scheduled_at: string;
  forecasts: Forecast[];
};

type Result = { ok: true; matches: UpcomingMatch[] } | { ok: false; error: string };

export function decodeMatches(value: unknown): UpcomingMatch[] {
  if (!Array.isArray(value)) throw new Error("Invalid match response");
  for (const match of value) {
    if (!match || !Number.isInteger(match.id) || !Number.isInteger(match.team1_id) ||
        (match.vlr_id !== null && !Number.isInteger(match.vlr_id)) ||
        (match.event_name !== null && typeof match.event_name !== "string") ||
        (match.stage !== null && typeof match.stage !== "string") ||
        !Number.isInteger(match.team2_id) || typeof match.team1_name !== "string" ||
        typeof match.team2_name !== "string" || !Number.isFinite(Date.parse(match.scheduled_at)) ||
        !Array.isArray(match.forecasts)) throw new Error("Invalid match response");
    for (const forecast of match.forecasts) {
      if (!forecast || !Number.isInteger(forecast.id) || forecast.match_id !== match.id ||
          !Number.isInteger(forecast.team1_id) || !Number.isInteger(forecast.team2_id) ||
          typeof forecast.source_key !== "string" || typeof forecast.source_type !== "string" ||
          !Number.isFinite(forecast.team1_win_probability) ||
          (forecast.rationale !== null && typeof forecast.rationale !== "string") ||
          !Number.isFinite(Date.parse(forecast.lock_time)) ||
          !Number.isFinite(Date.parse(forecast.created_at))) throw new Error("Invalid forecast response");
    }
  }
  return value as UpcomingMatch[];
}

export async function loadUpcoming(apiUrl: string, fetcher: typeof fetch = fetch): Promise<Result> {
  try {
    const response = await fetcher(`${apiUrl}/matches/upcoming/forecasts`, {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) throw new Error("Request failed");
    return { ok: true, matches: decodeMatches(await response.json()) };
  } catch {
    return { ok: false, error: "Match data is temporarily unavailable. Please try again shortly." };
  }
}

export function modelLabel(source: string): string {
  if (source.endsWith(":prospective-v1")) {
    return modelLabel(source.replace(":prospective-v1", ":observed-v1")).replace("observed history", "prospective") + " · frozen live";
  }
  const names: Record<string, string> = {
    "model:elo:v1": "Elo v1 · legacy",
    "model:elo:v1:observed-v1": "Elo v1 · observed history",
    "model:elo:v2:decay30:observed-v1": "Elo v2 · 30-day decay · experimental",
    "model:elo:v2:decay90:observed-v1": "Elo v2 · 90-day decay · experimental",
    "model:elo:v2:decay180:observed-v1": "Elo v2 · 180-day decay · experimental",
    "model:logistic:v1:observed-v1": "Logistic regression v1 · experimental",
    "model:boosting:v1:observed-v1": "Gradient boosting v1 · experimental",
    "model:ensemble:v1:observed-v1": "Equal-weight ensemble v1 · experimental",
  };
  return names[source] ?? source;
}
