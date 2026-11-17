"use client";
import { useEffect, useRef, useState } from "react";
import { formatTime, percent } from "@/lib/match-format";
import { getForecastDisplay } from "@/lib/forecast-display";
import { modelLabel, type UpcomingMatch } from "@/lib/upcoming";
import { matchTime } from "@/lib/match-time";
import { Icon } from "./icons";
import { TeamMark } from "./team-mark";

export function ForecastDialog({
  match,
  saved,
  toggle,
  close,
}: {
  match: UpcomingMatch;
  saved: boolean;
  toggle: () => void;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [section, setSection] = useState<"overview" | "evidence">("overview");
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  const p = match.current_preview;
  return (
    <dialog
      ref={ref}
      className="forecast-dialog"
      onClose={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close();
      }}
      aria-labelledby="forecast-title"
    >
      <div className="dialog-top">
        <span className="eyebrow">{match.event_name ?? "Match forecast"}</span>
        <button
          autoFocus
          className="icon-button"
          aria-label="Close forecast"
          onClick={() => ref.current?.close()}
        >
          <Icon name="close" />
        </button>
      </div>
      <div className="dialog-body">
        <p className="subtle">
          {matchTime(match.scheduled_at)} ET · {match.stage ?? "Scheduled"}
        </p>
        <h2 id="forecast-title">
          {match.team1_name}
          <span className="versus"> vs </span>
          {match.team2_name}
        </h2>
        <div className="dialog-outcomes">
          {[
            { name: match.team1_name, prob: p?.team1_win_probability },
            {
              name: match.team2_name,
              prob: p ? 1 - p.team1_win_probability : undefined,
            },
          ].map((t) => (
            <div key={t.name}>
              <TeamMark name={t.name} />
              <span>{t.name}</span>
              <strong>{percent(t.prob)}</strong>
            </div>
          ))}
        </div>
        <div className="detail-tabs" aria-label="Forecast details">
          <button
            aria-pressed={section === "overview"}
            onClick={() => setSection("overview")}
          >
            The matchup
          </button>
          <button
            aria-pressed={section === "evidence"}
            onClick={() => setSection("evidence")}
          >
            Forecast record
          </button>
        </div>
        {section === "overview" ? (
          <div className="detail-content">
            <h3>What’s behind the numbers</h3>
            <p>
              Each team’s Elo rating reflects its match results. The rating gap
              becomes a pre-match win probability, recalculated with the latest
              available history.
            </p>
            {p && (
              <>
                <div className="rating-table">
                  <div>
                    <span>Team</span>
                    <span>Elo</span>
                    <span>Series</span>
                  </div>
                  <div>
                    <strong>{match.team1_name}</strong>
                    <b>{Math.round(p.team1_rating)}</b>
                    <span>{p.team1_history_count}</span>
                  </div>
                  <div>
                    <strong>{match.team2_name}</strong>
                    <b>{Math.round(p.team2_rating)}</b>
                    <span>{p.team2_history_count}</span>
                  </div>
                </div>
                <p className="detail-note">
                  {p.history_count.toLocaleString("en-US")} historical series ·
                  Updated {formatTime(p.computed_at)}.
                </p>
                {(p.team1_unseen || p.team2_unseen) && (
                  <p className="notice">
                    A team without prior history starts at the 1500 Elo
                    baseline.
                  </p>
                )}
              </>
            )}
            <p className="detail-note">
              Current research estimate. Historical availability is incomplete;
              these probabilities are not a verified prospective performance
              record.
            </p>
          </div>
        ) : (
          <div className="detail-content">
            <h3>Saved before the match</h3>
            <p>
              Saved forecasts are frozen records. Their probabilities can differ
              from the current research estimate above.
            </p>
            {match.forecasts.length ? (
              match.forecasts.map((f) => (
                <div className="saved-record" key={f.id}>
                  <div>
                    <strong>
                      {percent(getForecastDisplay(match, f).team1Probability)}{" "}
                      <span>{match.team1_name}</span>
                    </strong>
                    <span>{formatTime(f.created_at)}</span>
                  </div>
                  <p>{modelLabel(f.source_key)}</p>
                  <p>{getForecastDisplay(match, f).description}</p>
                  <p>Locks {formatTime(f.lock_time)}</p>
                </div>
              ))
            ) : (
              <p className="notice">
                No saved forecast is available for this match.
              </p>
            )}
            <details className="provenance">
              <summary>Data provenance</summary>
              <p>
                Sources:{" "}
                {(match.sources ?? [])
                  .map((s) => s.source.toUpperCase())
                  .join(", ") || "VLR"}
              </p>
              {p && (
                <>
                  <p>Model: {p.source_key}</p>
                  <p>
                    Dataset: <code>{p.dataset_sha256}</code>
                  </p>
                  <p>
                    Base snapshot: <code>{p.base_dataset_sha256}</code>
                  </p>
                </>
              )}
            </details>
          </div>
        )}
        <div className="dialog-actions">
          <button
            className={`primary-button ${saved ? "saved" : ""}`}
            onClick={toggle}
          >
            <Icon name="star" filled={saved} />
            {saved ? "On your watchlist" : "Add to watchlist"}
          </button>
          {match.vlr_id && (
            <a
              className="text-link"
              href={`https://www.vlr.gg/${match.vlr_id}`}
              target="_blank"
              rel="noreferrer"
            >
              View on VLR ↗
            </a>
          )}
        </div>
      </div>
    </dialog>
  );
}
