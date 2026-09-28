"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useUpcoming } from "@/lib/use-upcoming";
import { formatTime, percent } from "@/lib/market";
import {
  discoverMatches,
  easternDay,
  favoriteProbability,
  readWatchlist,
  type BoardLens,
  type BoardSort,
} from "@/lib/discovery";
import { getForecastDisplay } from "@/lib/forecast-display";
import { modelLabel, type UpcomingMatch } from "@/lib/upcoming";
import LiveBoard from "./components/live-board";

type IconName =
  | "search"
  | "star"
  | "grid"
  | "list"
  | "arrow"
  | "close"
  | "live"
  | "chart"
  | "chevron"
  | "refresh";
function Icon({ name, filled = false }: { name: IconName; filled?: boolean }) {
  const paths: Record<IconName, string> = {
    search: "m21 21-4.5-4.5 M19 10.5a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0",
    star: "m12 3 2.8 5.7 6.3.9-4.6 4.4 1.1 6.3L12 17.3l-5.6 3 1.1-6.3L3 9.6l6.2-.9Z",
    grid: "M3 3h7v7H3Z M14 3h7v7h-7Z M3 14h7v7H3Z M14 14h7v7h-7Z",
    list: "M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01",
    arrow: "M5 12h14m-6-6 6 6-6 6",
    close: "m6 6 12 12M6 18 18 6",
    live: "M2 12h4l3-7 5 14 3-7h5",
    chart: "M4 19V9m8 10V4m8 15v-7",
    chevron: "m8 4 8 8-8 8",
    refresh:
      "M20 7v5h-5M4 17v-5h5M6.1 6.1a8 8 0 0 1 13.2 3M4.7 14.9a8 8 0 0 0 13.2 3",
  };
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
function TeamMark({ name, large = false }: { name: string; large?: boolean }) {
  const colors = ["#d8eee3", "#e9e0f3", "#f2e4d2", "#dce6f5", "#f3dfe0"];
  const hash = [...name].reduce((sum, c) => sum + c.charCodeAt(0), 0);
  const words = name
    .split(/\s+/)
    .filter((w) => !["team", "esports", "gaming"].includes(w.toLowerCase()));
  const initials =
    words.length === 1
      ? words[0].slice(0, 3)
      : words
          .map((w) => w[0])
          .join("")
          .slice(0, 3) || name.slice(0, 2);
  return (
    <span
      className={`team-mark ${large ? "large" : ""}`}
      style={{ background: colors[hash % colors.length] }}
    >
      {initials.toUpperCase()}
    </span>
  );
}
function matchTime(value: string, dateOnly = false) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    ...(dateOnly ? {} : { hour: "numeric", minute: "2-digit" }),
  }).format(new Date(value));
}
function MatchCard({
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
  return (
    <article className="match-card">
      <div className="card-top">
        <span className="event-label">
          {match.event_name?.replace(/^Valorant /i, "") ?? "Upcoming match"}
        </span>
        <button
          className={`icon-button save-button ${saved ? "is-saved" : ""}`}
          aria-label={`${saved ? "Remove" : "Save"} ${match.team1_name} vs ${match.team2_name}${saved ? " from" : " to"} watchlist`}
          aria-pressed={saved}
          onClick={toggle}
        >
          <Icon name="star" filled={saved} />
        </button>
      </div>
      <div className="card-schedule">
        <span>{matchTime(match.scheduled_at)} ET</span>
        <span>
          {match.stage?.replace(/^Group Stage[–—-]?/, "") ?? "Scheduled"}
        </span>
      </div>
      <h3 className="sr-only">
        {match.team1_name} vs {match.team2_name}
      </h3>
      {[
        { name: match.team1_name, p },
        { name: match.team2_name, p: p == null ? undefined : 1 - p },
      ].map((team) => (
        <button
          className="outcome-row"
          key={team.name}
          onClick={open}
          aria-label={`Explore ${team.name} forecast`}
        >
          <TeamMark name={team.name} />
          <span className="team-name">{team.name}</span>
          <span
            className={`probability ${team.p != null && team.p >= 0.5 ? "favored" : ""}`}
          >
            {percent(team.p)}
          </span>
        </button>
      ))}
      <div className="probability-track" aria-hidden="true">
        <span style={{ width: `${p == null ? 0 : p * 100}%` }} />
      </div>
      <div className="card-bottom">
        <span>{p == null ? "Awaiting model" : "Model probability"}</span>
        <button onClick={open}>
          Match details <Icon name="arrow" />
        </button>
      </div>
    </article>
  );
}
function ForecastDialog({
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
function AboutDialog({ close }: { close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className="forecast-dialog about-dialog"
      onClose={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close();
      }}
      aria-labelledby="about-title"
    >
      <div className="dialog-top">
        <span className="eyebrow">Built for the match</span>
        <button
          autoFocus
          className="icon-button"
          aria-label="Close model information"
          onClick={() => ref.current?.close()}
        >
          <Icon name="close" />
        </button>
      </div>
      <div className="dialog-body">
        <h2 id="about-title">A model. A point of view.</h2>
        <p>
          ClutchQuant estimates Valorant match outcomes using Elo ratings and
          real results from VLR.
        </p>
        <div className="model-facts">
          <div>
            <strong>1500</strong>
            <span>Starting rating</span>
          </div>
          <div>
            <strong>32</strong>
            <span>Elo K-factor</span>
          </div>
          <div>
            <strong>400</strong>
            <span>Rating scale</span>
          </div>
        </div>
        <h3>Read the board</h3>
        <p>
          Green highlights a team with at least a 50% model probability. Close
          calls are matchups where neither team exceeds 60%; strong leans have a
          favorite at 70% or higher.
        </p>
        <h3>Keep the distinction</h3>
        <p>
          The board shows current research estimates. Saved forecasts are
          timestamped, immutable records made before a match. Historical
          availability is incomplete, so retrospective results are not
          leakage-certified performance.
        </p>
        <p className="detail-note">
          This is a forecasting tool. There are no trades, market prices, or
          order books. Live estimates use available scores; side, economy, and
          map-specific effects are not modeled.
        </p>
      </div>
    </dialog>
  );
}
export default function Home() {
  const state = useUpcoming();
  const matches = state.data ?? [];
  const [query, setQuery] = useState("");
  const [event, setEvent] = useState("");
  const [day, setDay] = useState("");
  const [lens, setLens] = useState<BoardLens>("all");
  const [sort, setSort] = useState<BoardSort>("soonest");
  const [view, setView] = useState<"all" | "saved" | "live">("all");
  const [layout, setLayout] = useState<"grid" | "list">("grid");
  const [saved, setSaved] = useState<number[]>([]);
  const [storageWarning, setStorageWarning] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [about, setAbout] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        setSaved(readWatchlist(localStorage.getItem("cq-watchlist")));
      } catch {
        setStorageWarning(true);
      }
    }, 0);
    const key = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement) &&
        !document.querySelector("dialog[open]")
      ) {
        e.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("keydown", key);
    };
  }, []);
  function toggle(id: number) {
    const next = saved.includes(id)
      ? saved.filter((x) => x !== id)
      : [...saved, id];
    setSaved(next);
    try {
      localStorage.setItem("cq-watchlist", JSON.stringify(next));
    } catch {
      setStorageWarning(true);
    }
  }
  function reset() {
    setQuery("");
    setEvent("");
    setDay("");
    setLens("all");
    setSort("soonest");
  }
  const visible = discoverMatches(matches, {
    query,
    event,
    day,
    lens,
    sort,
    savedOnly: view === "saved",
    saved,
  });
  const events = [
    ...new Set(
      matches.map((m) => m.event_name).filter((e): e is string => !!e),
    ),
  ];
  const days = [
    ...new Set(matches.map((m) => easternDay(m.scheduled_at))),
  ].sort();
  const next = discoverMatches(matches, {
    query: "",
    event: "",
    day: "",
    lens: "all",
    sort: "soonest",
    savedOnly: false,
    saved,
  })[0];
  const selectedMatch = matches.find((m) => m.id === selected);
  const preview = matches.find((m) => m.current_preview)?.current_preview;
  const closeMatches = matches.filter((m) => {
    const p = favoriteProbability(m);
    return p !== null && p <= 0.6;
  });
  const savedCount = matches.filter((m) => saved.includes(m.id)).length;
  return (
    <div className="cq-app">
      <header className="site-header">
        <Link className="brand" href="/" aria-label="ClutchQuant home">
          <span className="brand-mark">
            cq<span>↗</span>
          </span>
          <span>
            ClutchQuant<span className="brand-dot">.</span>
          </span>
        </Link>
        <div className="search-box">
          <Icon name="search" />
          <input
            ref={search}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (view === "live") setView("all");
            }}
            placeholder="Find a team or tournament"
            aria-label="Search matches"
          />
          {query ? (
            <button aria-label="Clear search" onClick={() => setQuery("")}>
              <Icon name="close" />
            </button>
          ) : (
            <kbd>/</kbd>
          )}
        </div>
        <button
          className="header-watch"
          onClick={() => {
            setView("saved");
            reset();
          }}
        >
          <Icon name="star" />
          Watchlist<span>{savedCount}</span>
        </button>
      </header>
      <div className="app-layout">
        <aside className="sidebar">
          <div className="game-label">
            <span className="valorant-mark">V</span>VALORANT
          </div>
          <nav aria-label="Main navigation">
            <button
              className={view === "all" ? "active" : ""}
              onClick={() => {
                setView("all");
                reset();
              }}
            >
              <Icon name="grid" />
              Match board<span>{matches.length}</span>
            </button>
            <button
              className={view === "live" ? "active" : ""}
              onClick={() => setView("live")}
            >
              <Icon name="live" />
              Live scores
              <i className="live-dot" />
            </button>
            <button
              className={view === "saved" ? "active" : ""}
              onClick={() => {
                setView("saved");
                reset();
              }}
            >
              <Icon name="star" />
              Watchlist<span>{savedCount}</span>
            </button>
          </nav>
          <div className="sidebar-section">
            <p className="eyebrow">Tournaments</p>
            {events.length ? (
              events.map((e) => (
                <button
                  key={e}
                  className={event === e ? "event-active" : ""}
                  onClick={() => {
                    setView("all");
                    setEvent(event === e ? "" : e);
                    setDay("");
                  }}
                >
                  <span className="event-icon">◇</span>
                  {e.replace(/^Valorant /i, "")}
                  <Icon name="chevron" />
                </button>
              ))
            ) : (
              <p className="subtle">Waiting for the schedule</p>
            )}
          </div>
          <div className="sidebar-bottom">
            <button className="model-link" onClick={() => setAbout(true)}>
              <Icon name="chart" />
              <span>
                Inside the model<small>How the probabilities work</small>
              </span>
              <Icon name="arrow" />
            </button>
            <p>
              Independent research.
              <br />
              Built for Valorant.
            </p>
            <a
              href="https://github.com/nuIsaac/ClutchQuant"
              target="_blank"
              rel="noreferrer"
            >
              Open source ↗
            </a>
          </div>
        </aside>
        <main className="board-main">
          <div className="page-heading">
            <div>
              <p className="eyebrow">VALORANT · MATCH INTELLIGENCE</p>
              <h1>
                {view === "saved"
                  ? "Your watchlist"
                  : view === "live"
                    ? "In the server"
                    : "The match board"}
              </h1>
              <p>
                {view === "saved"
                  ? "The matchups you want to keep an eye on."
                  : view === "live"
                    ? "Score-conditioned probabilities, as the match unfolds."
                    : "A closer look at who takes the next series."}
              </p>
            </div>
            <button
              className="update-status"
              onClick={state.retry}
              aria-label="Refresh match data"
            >
              <i className={state.stale ? "status-dot stale" : "status-dot"} />
              <span>
                {state.phase === "loading"
                  ? "Connecting…"
                  : state.stale
                    ? "Cached data"
                    : state.phase === "error"
                      ? "Data unavailable"
                      : "Updated every minute"}
              </span>
              <Icon name="refresh" />
            </button>
          </div>
          {state.stale && (
            <div className="status-banner" role="status">
              Showing cached data. Refresh is unavailable; we’ll retry
              automatically.<button onClick={state.retry}>Retry now</button>
            </div>
          )}
          {storageWarning && (
            <div className="status-banner" role="status">
              Watchlist changes are available for this visit, but this browser
              couldn’t save them.
            </div>
          )}
          {view === "live" ? (
            <div className="live-surface">
              <LiveBoard />
            </div>
          ) : (
            <>
              {view === "all" &&
                !query &&
                !event &&
                !day &&
                lens === "all" &&
                next && (
                  <section
                    className="spotlight-row"
                    aria-label="Featured match"
                  >
                    <div className="spotlight">
                      <div className="spotlight-label">
                        <span>
                          <i className="status-dot" />
                          NEXT ON THE SCHEDULE
                        </span>
                        <span>{matchTime(next.scheduled_at)} ET</span>
                      </div>
                      <div className="spotlight-content">
                        <div>
                          <p className="eyebrow">{next.event_name}</p>
                          <h2>
                            {next.team1_name}
                            <span>vs {next.team2_name}</span>
                          </h2>
                          <button
                            className="spotlight-cta"
                            onClick={() => setSelected(next.id)}
                          >
                            Explore the matchup <Icon name="arrow" />
                          </button>
                        </div>
                        <div className="spotlight-teams" aria-hidden="true">
                          <TeamMark name={next.team1_name} large />
                          <span>VS</span>
                          <TeamMark name={next.team2_name} large />
                        </div>
                      </div>
                      <div className="spotlight-footer">
                        <span>MODEL WIN PROBABILITY</span>
                        <strong>
                          {percent(next.current_preview?.team1_win_probability)}{" "}
                          <span>/</span>{" "}
                          {percent(
                            next.current_preview
                              ? 1 - next.current_preview.team1_win_probability
                              : undefined,
                          )}
                        </strong>
                      </div>
                    </div>
                    <div className="radar">
                      <div className="radar-heading">
                        <span className="eyebrow">TOO CLOSE TO CALL?</span>
                        <Icon name="chart" />
                      </div>
                      <h2>
                        {closeMatches.length}
                        <span>
                          tight{" "}
                          {closeMatches.length === 1 ? "matchup" : "matchups"}
                        </span>
                      </h2>
                      <p>
                        Neither side above 60%.
                        <br />
                        These could go either way.
                      </p>
                      <button
                        onClick={() => {
                          setLens("close");
                          setSort("closest");
                        }}
                      >
                        Find the close calls <Icon name="arrow" />
                      </button>
                      <div className="radar-lines" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                  </section>
                )}
              <section className="matches-section" aria-label="Match forecasts">
                <div className="board-toolbar">
                  <div className="board-tabs" aria-label="Match categories">
                    {(
                      [
                        ["all", "All matches"],
                        ["close", "Close calls"],
                        ["strong", "Strong leans"],
                      ] as const
                    ).map(([value, label]) => (
                      <button
                        key={value}
                        aria-pressed={lens === value}
                        onClick={() => setLens(value)}
                      >
                        {label}
                        {value === "all" && (
                          <span>
                            {view === "saved" ? savedCount : matches.length}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                  <div className="display-controls">
                    <label className="sort-control">
                      <span className="sr-only">Sort matches</span>
                      <select
                        value={sort}
                        onChange={(e) => setSort(e.target.value as BoardSort)}
                      >
                        <option value="soonest">Soonest first</option>
                        <option value="closest">Closest matchup</option>
                        <option value="strongest">Strongest favorite</option>
                      </select>
                    </label>
                    <div className="layout-toggle" aria-label="Board layout">
                      <button
                        aria-label="Grid view"
                        aria-pressed={layout === "grid"}
                        onClick={() => setLayout("grid")}
                      >
                        <Icon name="grid" />
                      </button>
                      <button
                        aria-label="List view"
                        aria-pressed={layout === "list"}
                        onClick={() => setLayout("list")}
                      >
                        <Icon name="list" />
                      </button>
                    </div>
                  </div>
                </div>
                <div className="date-row" aria-label="Filter by match date">
                  <button aria-pressed={!day} onClick={() => setDay("")}>
                    All dates
                  </button>
                  {days.map((d) => (
                    <button
                      aria-pressed={day === d}
                      key={d}
                      onClick={() => setDay(d)}
                    >
                      {matchTime(
                        matches.find((m) => easternDay(m.scheduled_at) === d)!
                          .scheduled_at,
                        true,
                      )}
                    </button>
                  ))}
                  <span>Times in ET</span>
                </div>
                {event && (
                  <button className="filter-chip" onClick={() => setEvent("")}>
                    {event}
                    <Icon name="close" />
                  </button>
                )}
                <div className="results-announcement" aria-live="polite">
                  {state.data !== null &&
                  (query || day || event || lens !== "all")
                    ? `${visible.length} ${visible.length === 1 ? "match" : "matches"}${query ? ` for “${query}”` : ""}`
                    : ""}
                </div>
                {state.data === null ? (
                  state.phase === "error" ? (
                    <div className="empty-state" role="status">
                      <Icon name="refresh" />
                      <h2>Couldn’t load the match board.</h2>
                      <p>The data service is taking longer than expected.</p>
                      <button className="primary-button" onClick={state.retry}>
                        Try again <Icon name="arrow" />
                      </button>
                    </div>
                  ) : (
                    <div aria-busy="true" aria-label="Loading matches">
                      <p className="loading-copy" role="status">
                        Connecting to the data service. We’ll retry
                        automatically.
                      </p>
                      <div className="match-grid">
                        {[1, 2, 3, 4, 5, 6].map((n) => (
                          <div className="skeleton-card" key={n}>
                            <span />
                            <span />
                            <span />
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                ) : visible.length ? (
                  <div
                    className={`match-grid ${layout === "list" ? "list-layout" : ""}`}
                  >
                    {visible.map((m) => (
                      <MatchCard
                        key={m.id}
                        match={m}
                        saved={saved.includes(m.id)}
                        toggle={() => toggle(m.id)}
                        open={() => setSelected(m.id)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">
                    <Icon name={view === "saved" ? "star" : "search"} />
                    <h2>
                      {view === "saved" && !savedCount
                        ? "Your next favorite matchup goes here."
                        : "No matches in this view."}
                    </h2>
                    <p>
                      {view === "saved" && !savedCount
                        ? "Tap the star on any match to add it to your watchlist."
                        : "Try a different team, date, or filter."}
                    </p>
                    <button
                      className="primary-button"
                      onClick={() => {
                        reset();
                        if (view === "saved") setView("all");
                      }}
                    >
                      Explore all matches <Icon name="arrow" />
                    </button>
                  </div>
                )}
              </section>
            </>
          )}
          <footer className="board-footer">
            <span>
              <i className="status-dot" />
              Powered by Elo v1
              {preview
                ? ` · ${preview.history_count.toLocaleString("en-US")} historical series`
                : ""}
            </span>
            <button onClick={() => setAbout(true)}>
              Model probabilities. No trading. <Icon name="arrow" />
            </button>
          </footer>
        </main>
      </div>
      {selectedMatch && (
        <ForecastDialog
          key={selectedMatch.id}
          match={selectedMatch}
          saved={saved.includes(selectedMatch.id)}
          toggle={() => toggle(selectedMatch.id)}
          close={() => setSelected(null)}
        />
      )}
      {about && <AboutDialog close={() => setAbout(false)} />}
    </div>
  );
}
