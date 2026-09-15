import Link from "next/link";
import { loadUpcoming } from "@/lib/upcoming";
import { formatTime } from "@/lib/market";
import MarketBoard from "./components/market-board";
import { MetricCard } from "./components/market-primitives";
import LiveBoard from "./components/live-board";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1";
export default async function Home() {
  const upcoming = await loadUpcoming(API_URL);
  const matches = upcoming.ok ? upcoming.matches : [];
  const leaders = matches
    .filter((m) => m.current_preview)
    .sort(
      (a, b) =>
        Math.abs(b.current_preview!.team1_win_probability - 0.5) -
        Math.abs(a.current_preview!.team1_win_probability - 0.5),
    )
    .slice(0, 4);
  const history = matches.find((m) => m.current_preview)?.current_preview;
  return (
    <main className="min-h-screen bg-[#090d14] text-slate-100">
      <header className="border-b border-slate-800/70 bg-[#0d121c]">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-4 px-4 py-4 lg:px-8">
          <Link href="/" className="text-base font-black tracking-[.16em]">
            CLUTCH<span className="text-violet-400">QUANT</span>
          </Link>
          <nav
            className="order-3 flex w-full gap-6 text-xs font-medium text-slate-400 sm:order-none sm:w-auto"
            aria-label="Main navigation"
          >
            {[
              ["Markets", "markets"],
              ["Live", "live"],
              ["Models", "models"],
            ].map(([label, id]) => (
              <a key={id} href={`#${id}`} className="hover:text-violet-300">
                {label}
              </a>
            ))}
          </nav>
          <div className="text-[10px] text-slate-500">
            {upcoming.ok ? "Elo v1" : "Model unavailable"}
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-[1440px] px-4 py-6 lg:px-8">
        <section className="mb-5 flex flex-wrap items-end justify-between gap-5">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Valorant forecasts, quantified.
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Match probabilities from historical results.
            </p>
          </div>
          <p className="text-[10px] text-slate-500">
            Model computed
            <br />
            <span className="text-slate-400">
              {formatTime(history?.computed_at)}
            </span>
          </p>
        </section>
        <div
          id="models"
          className="mb-5 grid grid-cols-2 gap-y-4 rounded-lg bg-[#111722] py-4 sm:grid-cols-4"
        >
          <MetricCard
            label="Historical series"
            value={
              history?.history_count.toLocaleString("en-US") ?? "Unavailable"
            }
          />
          <MetricCard
            label="Upcoming forecasts"
            value={
              upcoming.ok
                ? String(matches.filter((m) => m.current_preview).length)
                : "Unavailable"
            }
          />
          <MetricCard
            label="Events"
            value={
              upcoming.ok
                ? String(
                    new Set(matches.map((m) => m.event_name).filter(Boolean))
                      .size,
                  )
                : "Unavailable"
            }
          />
          <MetricCard label="Model" value="Elo v1" note="1500 prior / K = 32" />
        </div>
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
          <section id="markets" className="min-w-0 scroll-mt-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Matches</h2>
              <span className="text-[10px] text-slate-500">
                Eastern time · up to 100 matches
              </span>
            </div>
            <LiveBoard />
            {upcoming.ok ? (
              <MarketBoard matches={matches} />
            ) : (
              <div
                role="alert"
                className="mt-4 rounded-lg bg-amber-950/30 p-6 text-sm text-amber-200"
              >
                {upcoming.error}
                <form action="/" method="get">
                  <button
                    type="submit"
                    className="mt-3 cursor-pointer underline"
                  >
                    Reload forecasts
                  </button>
                </form>
              </div>
            )}
          </section>
          <aside className="space-y-4 lg:pt-10">
            <section className="rounded-lg bg-[#111722] p-4">
              <h2 className="text-sm font-semibold">Strongest model leans</h2>
              <p className="mt-1 text-[10px] text-slate-500">
                Current probability · not market movement
              </p>
              <div className="mt-3 divide-y divide-slate-800">
                {leaders.map((m) => {
                  const p = m.current_preview!.team1_win_probability;
                  return (
                    <a
                      href={`#match-${m.id}`}
                      key={m.id}
                      className="flex items-center justify-between gap-2 py-3 text-xs"
                    >
                      <span className="min-w-0 truncate text-slate-300">
                        {p >= 0.5 ? m.team1_name : m.team2_name}
                      </span>
                      <span className="text-slate-500">View forecast</span>
                    </a>
                  );
                })}
                {!leaders.length && (
                  <p className="py-3 text-xs text-slate-500">
                    No current previews available.
                  </p>
                )}
              </div>
            </section>
          </aside>
        </div>
        <footer className="mt-6 border-t border-slate-800/70 pt-4 text-[10px] leading-5 text-slate-600">
          ClutchQuant / Valorant forecasting
        </footer>
      </div>
    </main>
  );
}
