type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

type UpcomingMatch = {
  id: number;
  vlr_id: number | null;
  team1_id: number;
  team1_name: string;
  team2_id: number;
  team2_name: string;
  event_name: string | null;
  stage: string | null;
  status: string;
  scheduled_at: string;
};

type Forecast = {
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
};

const API_URL = "http://127.0.0.1:8000/api/v1";

async function getHealth(): Promise<HealthResponse | null> {
  try {
    const response = await fetch(`${API_URL}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}

async function getUpcomingMatches(): Promise<UpcomingMatch[]> {
  try {
    const response = await fetch(`${API_URL}/matches/upcoming`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return [];
    }

    return response.json();
  } catch {
    return [];
  }
}

async function getForecasts(): Promise<Forecast[]> {
  try {
    const response = await fetch(`${API_URL}/forecasts`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return [];
    }

    return response.json();
  } catch {
    return [];
  }
}

function formatProbability(probability: number) {
  return `${(probability * 100).toFixed(1)}%`;
}

function formatMatchTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
    timeZoneName: "short",
  }).format(new Date(value));
}

export default async function Home() {
  const [health, matches, forecasts] = await Promise.all([
    getHealth(),
    getUpcomingMatches(),
    getForecasts(),
  ]);

  const eloForecasts = new Map(
    forecasts
      .filter((forecast) => forecast.source_key === "model:elo:v1")
      .map((forecast) => [forecast.match_id, forecast])
  );

  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="border-b border-zinc-800 pb-8">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <div>
              <p className="font-mono text-xs tracking-[0.35em] text-emerald-400">
                CLUTCHQUANT
              </p>

              <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
                Valorant forecasting,
                <span className="text-zinc-500"> quantified.</span>
              </h1>

              <p className="mt-4 max-w-2xl text-zinc-400">
                Data-driven match forecasts generated from historical
                competitive results and evaluated against real outcomes.
              </p>
            </div>

            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <span
                className={`h-2 w-2 rounded-full ${
                  health ? "bg-emerald-400" : "bg-red-400"
                }`}
              />

              {health ? "API connected" : "API unavailable"}
            </div>
          </div>
        </header>

        <section className="py-10">
          <div className="mb-6 flex items-end justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-500">
                MODEL FORECASTS
              </p>

              <h2 className="mt-1 text-2xl font-semibold">
                Upcoming matches
              </h2>
            </div>

            <p className="font-mono text-sm text-zinc-500">
              Elo v1
            </p>
          </div>

          {matches.length === 0 ? (
            <div className="border border-zinc-800 bg-zinc-900/40 p-8">
              <p className="font-medium">
                No upcoming matches found.
              </p>

              <p className="mt-2 text-sm text-zinc-500">
                Sync upcoming VLR matches to generate new forecasts.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {matches.map((match) => {
                const forecast = eloForecasts.get(match.id);

                const team1Probability =
                  forecast?.team1_win_probability ?? null;

                const team2Probability =
                  team1Probability === null
                    ? null
                    : 1 - team1Probability;

                const team1Favored =
                  team1Probability !== null &&
                  team1Probability >= 0.5;

                return (
                  <article
                    key={match.id}
                    className="border border-zinc-800 bg-zinc-900/40 p-6 transition hover:border-zinc-700"
                  >
                    <div className="flex flex-col gap-6">
                      <div className="flex flex-col justify-between gap-3 sm:flex-row">
                        <div>
                          <p className="text-sm text-zinc-400">
                            {match.event_name ?? "Unknown event"}
                          </p>

                          <p className="mt-1 text-xs text-zinc-600">
                            {match.stage ?? "Stage unavailable"}
                          </p>
                        </div>

                        <p className="font-mono text-xs text-zinc-500">
                          {formatMatchTime(match.scheduled_at)}
                        </p>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
                        <div>
                          <div className="flex items-center justify-between gap-4">
                            <p
                              className={`text-xl font-semibold ${
                                team1Favored
                                  ? "text-white"
                                  : "text-zinc-400"
                              }`}
                            >
                              {match.team1_name}
                            </p>

                            <p className="font-mono text-2xl">
                              {team1Probability === null
                                ? "—"
                                : formatProbability(
                                    team1Probability
                                  )}
                            </p>
                          </div>

                          {team1Probability !== null && (
                            <div className="mt-3 h-1.5 overflow-hidden bg-zinc-800">
                              <div
                                className="h-full bg-emerald-400"
                                style={{
                                  width: `${team1Probability * 100}%`,
                                }}
                              />
                            </div>
                          )}
                        </div>

                        <p className="text-center font-mono text-xs text-zinc-600">
                          VS
                        </p>

                        <div>
                          <div className="flex items-center justify-between gap-4 sm:flex-row-reverse">
                            <p
                              className={`text-xl font-semibold ${
                                team1Probability !== null &&
                                !team1Favored
                                  ? "text-white"
                                  : "text-zinc-400"
                              }`}
                            >
                              {match.team2_name}
                            </p>

                            <p className="font-mono text-2xl">
                              {team2Probability === null
                                ? "—"
                                : formatProbability(
                                    team2Probability
                                  )}
                            </p>
                          </div>

                          {team2Probability !== null && (
                            <div className="mt-3 h-1.5 overflow-hidden bg-zinc-800">
                              <div
                                className="h-full bg-zinc-500"
                                style={{
                                  width: `${team2Probability * 100}%`,
                                }}
                              />
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-col justify-between gap-2 border-t border-zinc-800 pt-4 text-xs sm:flex-row">
                        <p className="font-mono text-zinc-500">
                          {forecast?.rationale ??
                            "No Elo forecast generated"}
                        </p>

                        <p className="font-mono text-zinc-600">
                          MATCH #{match.id}
                        </p>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}