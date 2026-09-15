"use client";
import { useEffect, useState } from "react";
import { decodeLive, type LiveResponse } from "@/lib/live";
import { formatTime, percent } from "@/lib/market";
import { ProbabilityBar, ModelBadge } from "./market-primitives";

export default function LiveBoard() {
  const [data, setData] = useState<LiveResponse | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let mounted = true;
    let busy = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      if (busy) return;
      busy = true;
      let delay = 30000;
      if (!document.hidden) {
        try {
          const r = await fetch("/api/live", {
            cache: "no-store",
            signal: controller.signal,
          });
          if (!r.ok) throw Error("Unavailable");
          const next = decodeLive(await r.json());
          if (mounted) {
            setData(next);
            setFailed(false);
          }
          delay = next.poll_seconds * 1000;
        } catch {
          if (mounted) {
            setFailed(true);
            setData(null);
          }
        }
      }
      busy = false;
      if (mounted) timer = setTimeout(poll, delay);
    }
    function visibilityChanged() {
      if (document.hidden) setData(null);
      else {
        clearTimeout(timer);
        void poll();
      }
    }
    document.addEventListener("visibilitychange", visibilityChanged);
    void poll();
    return () => {
      mounted = false;
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visibilityChanged);
    };
  }, []);
  return (
    <section id="live" className="mb-5 scroll-mt-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Live</h2>
        <span className="text-[10px] text-slate-500">
          30-second polling when active
        </span>
      </div>
      {failed || data?.source_status === "unavailable" ? (
        <p
          role="status"
          className="rounded bg-slate-900 p-3 text-xs text-slate-400"
        >
          Live feed temporarily unavailable.
        </p>
      ) : !data ? (
        <p className="p-3 text-xs text-slate-500">Checking live matches…</p>
      ) : data.items.length === 0 ? (
        <p className="rounded bg-slate-900/50 p-3 text-xs text-slate-500">
          {data.active_listed
            ? "Live matches reported; waiting for usable scores."
            : "No live matches reported by the source."}
        </p>
      ) : null}
      {data?.source_status === "partial" && (
        <p className="mb-2 text-xs text-amber-300">
          Some live states are unavailable. Coverage is limited to{" "}
          {data.coverage_limit} matches.
        </p>
      )}
      <div className="grid items-start gap-2 sm:grid-cols-2">
        {data?.items.map((m) => (
          <article
            key={m.vlr_id}
            className="rounded-lg border border-violet-500/20 bg-[#111722] p-4"
          >
            <div className="mb-3 flex items-center gap-2">
              <ModelBadge current>
                {m.status === "live" ? "LIVE" : "FINAL"}
              </ModelBadge>
              <span className="text-xs text-slate-400">
                {m.map_name ??
                  (m.map_number ? `Map ${m.map_number}` : `BO${m.best_of}`)}
                {m.round_score ? ` · ${m.round_score.join("–")}` : ""}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">{m.team1_name}</h3>
              <span className="font-mono text-2xl text-violet-300">
                {percent(m.team1_win_probability)}
              </span>
            </div>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-sm font-semibold">{m.team2_name}</p>
              <span className="font-mono text-2xl text-cyan-200">
                {percent(
                  m.team1_win_probability === null
                    ? null
                    : 1 - m.team1_win_probability,
                )}
              </span>
            </div>
            <ProbabilityBar probability={m.team1_win_probability} />
            <p className="mt-2 text-xs text-slate-400">
              Series {m.series_score.join("–")} · BO{m.best_of}
            </p>
            {m.reason && (
              <p className="mt-2 text-[10px] text-amber-300">{m.reason}</p>
            )}
            <details className="mt-3 border-t border-slate-800 pt-2 text-xs text-slate-400">
              <summary className="cursor-pointer">View forecast</summary>
              <div className="mt-3 space-y-2">
                <p>Pre-match model: {percent(m.pre_match_probability)}</p>
                <p>Current map: {percent(m.current_map_probability)}</p>
                <p>
                  Elo: {m.team1_rating?.toFixed(0) ?? "Unavailable"} /{" "}
                  {m.team2_rating?.toFixed(0) ?? "Unavailable"}
                </p>
                <p>
                  Rating difference: {m.team1_rating !== null && m.team2_rating !== null
                    ? (m.team1_rating - m.team2_rating).toFixed(0)
                    : "Unavailable"}
                </p>
                <p>
                  {m.history_count.toLocaleString("en-US")} historical series ·{" "}
                  {m.model_version}
                </p>
                <p>
                  State received {formatTime(m.observed_at)}. Source latency is
                  unknown.
                </p>
                <p>
                  Score-conditioned estimate. Side, economy and map-specific
                  effects are not estimated.
                </p>
                <a
                  className="inline-block text-violet-300 underline"
                  href={`https://www.vlr.gg/${m.vlr_id}/`}
                  target="_blank"
                  rel="noreferrer"
                >
                  VLR match ↗
                </a>
              </div>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}
