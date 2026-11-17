"use client";
import { percent } from "@/lib/match-format";
import type { UpcomingMatch } from "@/lib/upcoming";
import { matchTime } from "@/lib/match-time";
import { Icon } from "./icons";
import { TeamMark } from "./team-mark";

export function MatchCard({
  match,
  saved,
  toggle,
  open,
}: {
  match: UpcomingMatch;
  saved: boolean;
  toggle: () => void;
  open: () => void;
}) {
  const p = match.current_preview?.team1_win_probability;
  const time = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(match.scheduled_at));
  return (
    <article className="match-card">
      <time className="match-start" dateTime={match.scheduled_at}>
        <strong>{matchTime(match.scheduled_at, true)}</strong>
        <span>{time} ET</span>
      </time>
      <button
        className="fixture"
        onClick={open}
        aria-label={`Explore ${match.team1_name} vs ${match.team2_name} forecast`}
      >
        <span>
          <TeamMark name={match.team1_name} />
          <span>{match.team1_name}</span>
        </span>
        <span>
          <TeamMark name={match.team2_name} />
          <span>{match.team2_name}</span>
        </span>
      </button>
      <div
        className="match-probability"
        aria-label={`Win probabilities: ${match.team1_name} ${percent(p)}, ${match.team2_name} ${percent(p == null ? undefined : 1 - p)}`}
      >
        <div>
          <strong className={p != null && p >= 0.5 ? "favored" : ""}>
            {percent(p)}
          </strong>
          <span>/</span>
          <strong className={p != null && p < 0.5 ? "favored" : ""}>
            {percent(p == null ? undefined : 1 - p)}
          </strong>
        </div>
        <div className="probability-track" aria-hidden="true">
          <span style={{ width: `${p == null ? 0 : p * 100}%` }} />
        </div>
        <small>{p == null ? "Estimate unavailable" : "Current estimate"}</small>
      </div>
      <div className="match-context">
        <span>{match.event_name ?? "Tournament unavailable"}</span>
        <small>{match.stage ?? "Scheduled"}</small>
      </div>
      <div className="match-actions">
        <button
          className={`icon-button save-button ${saved ? "is-saved" : ""}`}
          aria-label={`${saved ? "Remove" : "Save"} ${match.team1_name} vs ${match.team2_name}${saved ? " from" : " to"} watchlist`}
          aria-pressed={saved}
          onClick={toggle}
        >
          <Icon name="star" filled={saved} />
        </button>
        <button
          className="icon-button details-button"
          onClick={open}
          aria-label={`Match details: ${match.team1_name} vs ${match.team2_name}`}
        >
          <Icon name="arrow" />
        </button>
      </div>
    </article>
  );
}
