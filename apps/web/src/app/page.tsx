import Link from "next/link";
import { loadUpcoming } from "@/lib/upcoming";
import { loadProspective } from "@/lib/prospective";
import { formatTime, percent } from "@/lib/market";
import MarketBoard from "./components/market-board";
import { MetricCard, ModelBadge } from "./components/market-primitives";
import AuditTable from "./components/audit-table";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1";
export default async function Home() {
  const [upcoming, report] = await Promise.all([
    loadUpcoming(API_URL),
    loadProspective(API_URL),
  ]);
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
              ["Forecasts", "forecasts"],
              ["Models", "models"],
              ["Performance", "performance"],
            ].map(([label, id]) => (
              <a key={id} href={`#${id}`} className="hover:text-violet-300">
                {label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2 text-[10px] text-slate-500">
            <span
              className={`h-1.5 w-1.5 rounded-full ${report?.last_run_status === "SUCCEEDED" ? "bg-cyan-300" : "bg-amber-400"}`}
            />
            <span>
              ELO v1 ·{" "}
              {report?.last_run_status === "SUCCEEDED"
                ? "LAST RUN OK"
                : "STATUS UNAVAILABLE"}
            </span>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-[1440px] px-4 py-6 lg:px-8">
        <section className="mb-5 flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="mb-1 text-[10px] uppercase tracking-[.2em] text-violet-400">
              VALORANT / FORECAST TERMINAL
            </p>
            <h1 className="text-2xl font-semibold tracking-tight">
              Valorant forecasts, quantified.
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Match probabilities from historical results.
            </p>
          </div>
          <p className="text-[10px] text-slate-500">
            Last pipeline update
            <br />
            <span className="text-slate-400">
              {formatTime(report?.last_run_at)}
            </span>
          </p>
        </section>
        <div className="mb-5 grid grid-cols-2 gap-y-4 rounded-lg bg-[#111722] py-4 sm:grid-cols-4">
          <MetricCard
            label="Historical series"
            value={history?.history_count.toLocaleString("en-US") ?? "?"}
            note="Research model history"
          />
          <MetricCard
            label="Upcoming forecasts"
            value={
              upcoming.ok
                ? String(matches.filter((m) => m.current_preview).length)
                : "?"
            }
            note="Current model"
          />
          <MetricCard
            label="Events"
            value={
              upcoming.ok
                ? String(
                    new Set(matches.map((m) => m.event_name).filter(Boolean))
                      .size,
                  )
                : "?"
            }
            note="Upcoming tournaments"
          />
          <MetricCard label="Model" value="Elo v1" note="1500 prior ? K = 32" />
        </div>
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
          <section id="markets" className="min-w-0 scroll-mt-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Upcoming forecasts</h2>
              <span className="text-[10px] text-slate-500">
                Eastern time · up to 100 matches
              </span>
            </div>
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
                      href="#forecasts"
                      key={m.id}
                      className="flex items-center justify-between gap-2 py-3 text-xs"
                    >
                      <span className="min-w-0 truncate text-slate-300">
                        {p >= 0.5 ? m.team1_name : m.team2_name}
                      </span>
                      <span className="font-mono text-violet-300">
                        {percent(Math.max(p, 1 - p))}
                      </span>
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
            <section
              id="models"
              className="scroll-mt-4 rounded-lg bg-[#111722] p-4"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">Model desk</h2>
                <ModelBadge current>ELO v1</ModelBadge>
              </div>
              <p className="mt-3 font-mono text-2xl">
                {history?.history_count.toLocaleString("en-US") ?? "—"}
              </p>
              <p className="text-[10px] text-slate-500">
                Historical series in current research state
              </p>
              <p className="mt-4 text-xs leading-5 text-slate-400">
                Elo ratings update with completed series. New teams start at
                1500.
              </p>
              <div className="mt-3 border-t border-slate-800 pt-3 text-[10px] leading-5 text-slate-500">
                1500 starting rating · K = 32
                <br />
                Research model
                <br />
                Unseen teams retain the starting prior
              </div>
            </section>
          </aside>
        </div>
        <details
          id="performance"
          className="mt-5 scroll-mt-4 border-t border-slate-800/70 pt-5"
        >
          <summary className="mb-4 cursor-pointer text-sm text-slate-400">
            Methodology &amp; prospective evaluation
          </summary>
          <p className="mb-4 text-xs text-slate-500">
            Metrics use frozen prospective forecasts, not the current research
            model. Small samples are preliminary.
          </p>
          {!report ? (
            <p className="text-sm text-amber-300">
              Evaluation is temporarily unavailable.
            </p>
          ) : (
            <>
              {Object.entries(report.models).map(([key, m]) => (
                <div key={key} className="mb-3 rounded-lg bg-[#111722] p-4">
                  <p className="mb-4 break-all font-mono text-[10px] text-slate-400">
                    {key}
                  </p>
                  <div className="grid grid-cols-2 gap-y-4 sm:grid-cols-4">
                    <MetricCard label="Accuracy" value={percent(m.accuracy)} />
                    <MetricCard label="Brier" value={m.brier.toFixed(3)} />
                    <MetricCard
                      label="Log loss"
                      value={m.log_loss.toFixed(3)}
                    />
                    <MetricCard label="Resolved" value={String(m.count)} />
                  </div>
                  <p className="mt-4 text-[10px] text-slate-500">
                    Calibration:{" "}
                    {m.calibration_status.toLowerCase().replaceAll("_", " ")} ·
                    Descriptive results; no superiority claim. Research previews
                    are excluded.
                  </p>
                </div>
              ))}
              {!Object.keys(report.models).length && (
                <p className="text-sm text-slate-400">
                  No verified prospective outcomes yet.
                </p>
              )}
              <AuditTable records={report.records} total={report.total} />
            </>
          )}
        </details>
        <footer className="mt-6 border-t border-slate-800/70 pt-4 text-[10px] leading-5 text-slate-600">
          CLUTCHQUANT · Forecasting &amp; research. No trading, prices or
          payouts. Current previews are not prospective performance claims.
        </footer>
      </div>
    </main>
  );
}
