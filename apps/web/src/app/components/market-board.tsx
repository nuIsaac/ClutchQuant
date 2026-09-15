"use client";
import { useState } from "react";
import type { UpcomingMatch } from "@/lib/upcoming";
import { getForecastDisplay } from "@/lib/forecast-display";
import { eventFilters, matchesEvent, formatTime, percent } from "@/lib/market";
import { ModelBadge, ProbabilityBar } from "./market-primitives";

export function EventFilter({
  active,
  onChange,
}: {
  active: string;
  onChange: (value: string) => void;
}) {
  return (
    <div
      className="flex gap-2 overflow-x-auto py-3"
      aria-label="Filter tournaments"
    >
      {eventFilters.map((event) => (
        <button
          key={event}
          type="button"
          aria-pressed={event === active}
          onClick={() => onChange(event)}
          className={`shrink-0 cursor-pointer rounded-full px-3 py-1.5 text-xs ${event === active ? "bg-slate-100 font-semibold text-slate-950" : "bg-slate-900 text-slate-400 hover:text-white"}`}
        >
          {event}
        </button>
      ))}
    </div>
  );
}
export function ForecastDetail({ match }: { match: UpcomingMatch }) {
  const p = match.current_preview;
  return (
    <details className="mt-3 border-t border-slate-800/70 pt-2">
      <summary className="cursor-pointer text-xs text-slate-300 hover:text-white">
        View forecast ↗
      </summary>
      <div className="mt-3 space-y-3 text-xs text-slate-400">
        {p && (
          <>
            <p className="text-slate-200">Current model preview · Elo v1</p>
            <p className="font-mono text-lg text-slate-100">
              {percent(p.team1_win_probability)} /{" "}
              {percent(1 - p.team1_win_probability)}
            </p>
            <dl className="grid grid-cols-2 gap-2">
              <div>
                <dt>{match.team1_name} Elo</dt>
                <dd className="font-mono text-slate-100">
                  {p.team1_rating.toFixed(0)} · {p.team1_history_count} series
                </dd>
              </div>
              <div>
                <dt>{match.team2_name} Elo</dt>
                <dd className="font-mono text-slate-100">
                  {p.team2_rating.toFixed(0)} · {p.team2_history_count} series
                </dd>
              </div>
            </dl>
            <p>
              Rating difference: {(p.team1_rating - p.team2_rating).toFixed(0)}{" "}
              · {p.history_count.toLocaleString("en-US")} historical series
            </p>
            <p>Updated {formatTime(p.computed_at)}.</p>
            {(p.team1_unseen || p.team2_unseen) && (
              <p className="text-amber-300">
                1500 cold-start prior:{" "}
                {[
                  p.team1_unseen ? match.team1_name : null,
                  p.team2_unseen ? match.team2_name : null,
                ]
                  .filter(Boolean)
                  .join(", ")}
              </p>
            )}
          </>
        )}
        <details className="rounded bg-slate-950 p-2">
          <summary className="cursor-pointer">
            Advanced · provenance &amp; evidence
          </summary>
          <p className="mt-2">
            Match #{match.id}. Historical availability is unknown for research
            previews. This value was not necessarily known at the original lock
            time.
          </p>
          {p && (
            <p className="mt-2 break-all font-mono">
              {p.source_key}
              <br />
              State {p.dataset_sha256}
              <br />
              Base {p.base_dataset_sha256}
              <br />
              Exported {formatTime(p.base_exported_at)}
            </p>
          )}
          {match.forecasts.map((f) => {
            const d = getForecastDisplay(match, f);
            return (
              <div key={f.id} className="border-t border-slate-800 pt-2">
                <p className="text-slate-200">
                  {f.source_key.endsWith(":prospective-v1")
                    ? "Frozen prospective forecast"
                    : "Other saved forecast"}{" "}
                  · {percent(d.team1Probability)} /{" "}
                  {percent(
                    d.team1Probability === null ? null : 1 - d.team1Probability,
                  )}
                </p>
                <p className="mt-1">
                  Created {formatTime(f.created_at)} · lock{" "}
                  {formatTime(f.lock_time)}
                </p>
                <p className="mt-1">{d.description}</p>
              </div>
            );
          })}
          {match.forecasts.map((f) => (
            <p key={f.id} className="mt-2 break-all font-mono">
              Forecast #{f.id} · {f.source_key}
              <br />
              Run {f.model_run_id ?? "Unavailable"}
              <br />
              Saved probability {percent(f.team1_win_probability)}
            </p>
          ))}
        </details>
        {match.vlr_id !== null && (
          <a
            href={`https://www.vlr.gg/${match.vlr_id}`}
            target="_blank"
            rel="noreferrer"
            className="inline-block text-violet-300 underline"
          >
            Match details on VLR ↗
          </a>
        )}
      </div>
    </details>
  );
}
export function MarketCard({ match }: { match: UpcomingMatch }) {
  const p = match.current_preview?.team1_win_probability ?? null;
  return (
    <article className="min-w-0 rounded-lg bg-[#111722] p-4 transition-colors hover:bg-[#151c29]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-400">
        <span className="truncate">{match.stage ?? "Stage unavailable"}</span>
        <time dateTime={match.scheduled_at}>
          {formatTime(match.scheduled_at)}
        </time>
      </div>
      <div className="flex items-center justify-between gap-3">
        <h3 className="truncate text-sm font-semibold">{match.team1_name}</h3>
        <span className="font-mono text-2xl font-semibold tabular-nums text-violet-300">
          {percent(p)}
        </span>
      </div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="truncate text-sm font-semibold">{match.team2_name}</p>
        <span className="font-mono text-2xl font-semibold tabular-nums text-cyan-200">
          {percent(p === null ? null : 1 - p)}
        </span>
      </div>
      <ProbabilityBar probability={p} />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <ModelBadge current>CURRENT MODEL</ModelBadge>
        <span className="text-[10px] text-slate-400">Elo v1</span>
      </div>
      {p === null && (
        <p className="mt-2 text-xs text-amber-300">Preview unavailable</p>
      )}
      <ForecastDetail match={match} />
    </article>
  );
}
export default function MarketBoard({ matches }: { matches: UpcomingMatch[] }) {
  const [filter, setFilter] = useState("All");
  const shown = matches.filter((m) => matchesEvent(m, filter));
  const groups = new Map<string, UpcomingMatch[]>();
  for (const m of shown) {
    const event = m.event_name ?? "Unknown event";
    groups.set(event, [...(groups.get(event) ?? []), m]);
  }
  return (
    <div>
      <EventFilter active={filter} onChange={setFilter} />
      <div id="forecasts" className="scroll-mt-20">
        {!shown.length && (
          <p className="rounded-lg bg-slate-900 p-6 text-sm text-slate-400">
            No upcoming matches in this category.
          </p>
        )}
        {[...groups].map(([event, items]) => (
          <section key={event} className="mb-5">
            <h2 className="mb-2 mt-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-violet-400" />
              {event}
              <span className="font-mono text-slate-600">{items.length}</span>
            </h2>
            <div className="grid items-start gap-2 sm:grid-cols-2">
              {items.map((m) => (
                <MarketCard key={m.id} match={m} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
