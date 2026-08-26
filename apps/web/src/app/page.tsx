type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

async function getApiHealth(): Promise<HealthResponse | null> {
  try {
    const response = await fetch(
      "http://127.0.0.1:8000/api/v1/health",
      { cache: "no-store" }
    );

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await getApiHealth();

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 px-6 text-white">
      <section className="w-full max-w-3xl">
        <p className="mb-4 font-mono text-sm tracking-widest text-emerald-400">
          CLUTCHQUANT
        </p>

        <h1 className="text-5xl font-bold tracking-tight sm:text-7xl">
          Turn competitive instinct into measurable forecasts.
        </h1>

        <p className="mt-6 max-w-2xl text-lg leading-8 text-zinc-400">
          A Valorant quantitative research platform for recording predictions,
          evaluating calibration, and comparing human judgment with models.
        </p>

        <div className="mt-10 flex items-center gap-3 border border-zinc-800 bg-zinc-900 p-4">
          <span
            className={`h-3 w-3 rounded-full ${
              health ? "bg-emerald-400" : "bg-red-400"
            }`}
          />

          <div>
            <p className="font-semibold">
              {health ? "API connected" : "API unavailable"}
            </p>

            <p className="font-mono text-sm text-zinc-500">
              {health
                ? `${health.service} · v${health.version}`
                : "Start FastAPI on port 8000"}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}