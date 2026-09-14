import { getForecastDisplay } from "@/lib/forecast-display";
import { loadUpcoming, modelLabel } from "@/lib/upcoming";
import { Suspense } from "react";
import ProspectiveHistory from "./prospective-history";

const API_URL =
  process.env.API_URL ??
  "http://127.0.0.1:8000/api/v1";

function matchTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    timeZone: "America/New_York", timeZoneName: "short",
  }).format(new Date(value));
}

function probability(value: number | null) {
  return value === null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}

export default async function Home() {
  const result = await loadUpcoming(API_URL);
  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="border-b border-zinc-800 pb-8">
          <p className="font-mono text-xs tracking-[0.35em] text-emerald-400">CLUTCHQUANT</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">Valorant forecasting,<span className="text-zinc-500"> quantified.</span></h1>
          <p className="mt-4 max-w-2xl text-zinc-400">Compare recorded win probabilities, model versions, and the evidence behind each forecast.</p>
        </header>
        <section className="py-10" aria-labelledby="upcoming-heading">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <h2 id="upcoming-heading" className="text-2xl font-semibold">Upcoming matches</h2>
            <p className="text-sm text-zinc-400">All times Eastern · up to 100 scheduled matches</p>
          </div>
          {!result.ok ? (
            <div role="alert" className="rounded border border-amber-900 bg-amber-950/20 p-8">
              <p>{result.error}</p>
              <form action="/" method="get"><button type="submit" className="mt-3 cursor-pointer text-emerald-400 underline">Reload matches</button></form>
            </div>
          ) : result.matches.length === 0 ? (
            <div className="rounded border border-zinc-800 p-8">
              <p>No upcoming matches are currently scheduled.</p>
              <p className="mt-2 text-sm text-zinc-400">New matchups will appear after the next successful data update.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {result.matches.map((match) => (
                <article key={match.id} className="rounded border border-zinc-800 bg-zinc-900/40 p-5 sm:p-6">
                  <div className="flex flex-wrap justify-between gap-3 text-sm text-zinc-400">
                    <p>{match.event_name ?? "Unknown event"} · {match.stage ?? "Stage unavailable"}</p>
                    <time dateTime={match.scheduled_at}>{matchTime(match.scheduled_at)}</time>
                  </div>
                  <h3 className="my-5 text-2xl font-semibold">{match.team1_name}<span className="px-3 text-sm font-normal text-zinc-500">vs.</span>{match.team2_name}</h3>
                  {match.forecasts.length === 0 ? (
                    <p className="border-t border-zinc-800 py-4 text-sm text-zinc-400">No forecast has been recorded for this matchup.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm">
                        <caption className="sr-only">Recorded forecasts for {match.team1_name} versus {match.team2_name}</caption>
                        <thead className="border-b border-zinc-800 text-zinc-400"><tr>
                          <th scope="col" className="py-3 pr-4 font-normal">Model / source</th>
                          <th scope="col" className="px-3 py-3 text-right font-normal">{match.team1_name}</th>
                          <th scope="col" className="py-3 pl-3 text-right font-normal">{match.team2_name}</th>
                        </tr></thead>
                        <tbody>{match.forecasts.map((forecast) => {
                          const display = getForecastDisplay(match, forecast);
                          return (
                            <tr key={forecast.id} className="border-b border-zinc-800/70 align-top">
                              <th scope="row" className="py-4 pr-4 font-normal">
                                <span>{modelLabel(forecast.source_key)}</span>
                                <details className="mt-2 text-xs text-zinc-400">
                                  <summary className="cursor-pointer text-emerald-400">Forecast details</summary>
                                  <p className="mt-2 max-w-lg">{display.description}</p>
                                  <p className="mt-2">Recorded {matchTime(forecast.created_at)} · locks {matchTime(forecast.lock_time)}</p>
                                  <p className="mt-2 break-all font-mono">{forecast.model_run_id ? `Run ${forecast.model_run_id}` : "Historical run provenance unavailable"}</p>
                                </details>
                              </th>
                              <td className="px-3 py-4 text-right font-mono">{probability(display.team1Probability)}</td>
                              <td className="py-4 pl-3 text-right font-mono">{probability(display.team1Probability === null ? null : 1-display.team1Probability)}</td>
                            </tr>
                          );
                        })}</tbody>
                      </table>
                    </div>
                  )}
                  {match.vlr_id !== null && <a className="mt-4 inline-block text-xs text-emerald-400 underline" href={`https://www.vlr.gg/${match.vlr_id}`} target="_blank" rel="noreferrer">Match details on VLR</a>}
                </article>
              ))}
            </div>
          )}
        </section>
        <Suspense fallback={<p className="py-8 text-zinc-400">Loading prediction history…</p>}><ProspectiveHistory apiUrl={API_URL} /></Suspense>
        <footer className="border-t border-zinc-800 pt-5 text-xs leading-6 text-zinc-500">Experimental models are labeled individually. A missing forecast is not a 50% prediction. No consensus is shown unless an ensemble forecast has been explicitly recorded.</footer>
      </div>
    </main>
  );
}
