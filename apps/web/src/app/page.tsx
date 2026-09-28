"use client";
import Link from "next/link";
import { useUpcoming } from "@/lib/use-upcoming";
import { formatTime } from "@/lib/market";
import MarketBoard from "./components/market-board";
import { MetricCard } from "./components/market-primitives";
import LiveBoard from "./components/live-board";

export default function Home() {
  const state = useUpcoming();
  const upcoming = { ok: state.data !== null };
  const matches = state.data ?? [];
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
            {upcoming.ok ? "Elo v1" : "Connecting to data service"}
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
              {upcoming.ok ? formatTime(history?.computed_at) : "—"}
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
              history?.history_count.toLocaleString("en-US") ?? "—"
            }
          />
          <MetricCard
            label="Upcoming forecasts"
            value={
              upcoming.ok
                ? String(matches.filter((m) => m.current_preview).length)
                : "—"
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
                : "—"
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
            {upcoming.ok && <LiveBoard />}
            {state.stale && <p role="status" className="mt-3 text-xs text-amber-200">Showing cached data — {state.phase === "loading" ? "updating…" : "update unavailable. Retrying automatically."}</p>}
            {upcoming.ok ? (
              <MarketBoard matches={matches} />
            ) : (
              <div role={state.phase === "error" ? "alert" : "status"}
                aria-live="polite" className="mt-4 rounded-lg bg-[#111722] p-6 text-sm text-slate-300">
                {state.phase === "error" ? (
                  <><p>Couldn&apos;t load match data.</p><button onClick={state.retry} className="mt-3 cursor-pointer underline">Retry</button></>
                ) : (
                  <><p className="animate-pulse">ClutchQuant is loading match data…</p>
                  <p className="mt-2 text-xs text-slate-500">Connecting to the data service. Startup can take around 30 seconds; we&apos;ll retry automatically.</p></>
                )}
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
                    {upcoming.ok ? "No current previews available." : "Waiting for match data…"}
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
