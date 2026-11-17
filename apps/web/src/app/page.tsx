"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useUpcoming } from "@/lib/use-upcoming";
import { percent } from "@/lib/match-format";
import {
  discoverMatches,
  easternDay,
  favoriteProbability,
  type BoardLens,
  type BoardSort,
} from "@/lib/discovery";
import LiveBoard from "./components/live-board";

import { loadWatchlist, saveWatchlist } from "@/lib/watchlist";
import { matchTime } from "@/lib/match-time";
import { REPOSITORY_URL } from "@/lib/brand";
import { Icon } from "./components/icons";
import { TeamMark } from "./components/team-mark";
import { MatchCard } from "./components/match-card";
import { ForecastDialog } from "./components/forecast-dialog";
import { AboutDialog } from "./components/about-dialog";

export default function Home() {
  const state = useUpcoming();
  const matches = state.data ?? [];
  const [query, setQuery] = useState("");
  const [event, setEvent] = useState("");
  const [day, setDay] = useState("");
  const [lens, setLens] = useState<BoardLens>("all");
  const [sort, setSort] = useState<BoardSort>("soonest");
  const [view, setView] = useState<"all" | "saved" | "live">("all");
  const [layout, setLayout] = useState<"grid" | "list">("list");
  const [saved, setSaved] = useState<number[]>([]);
  const [storageWarning, setStorageWarning] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [about, setAbout] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        setSaved(loadWatchlist(localStorage));
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
      saveWatchlist(localStorage, next);
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
  const covered = matches.filter((match) => match.current_preview).length;
  return (
    <div className="twelve-twelve-app">
      <a className="skip-link" href="#main-content">
        Skip to matches
      </a>
      <header className="site-header">
        <Link
          className="brand"
          href="/"
          aria-label="12:12 — twelve to twelve home"
        >
          <span className="wordmark">
            12<span className="wordmark-colon">:</span>12
          </span>
        </Link>
        <span className="workspace-label">VALORANT INTELLIGENCE</span>
        <nav className="main-nav" aria-label="Main navigation">
          <button
            aria-current={view === "all" ? "page" : undefined}
            onClick={() => {
              setView("all");
              reset();
            }}
          >
            Matches
          </button>
          <button
            aria-current={view === "live" ? "page" : undefined}
            onClick={() => setView("live")}
          >
            Live
          </button>
          <button
            aria-current={view === "saved" ? "page" : undefined}
            onClick={() => {
              setView("saved");
              reset();
            }}
          >
            Watchlist <span>{savedCount}</span>
          </button>
        </nav>
        <button className="header-model" onClick={() => setAbout(true)}>
          <Icon name="chart" />
          <span>Model notes</span>
        </button>
      </header>
      <main id="main-content" className="workspace">
        <div className="page-heading">
          <div>
            <p className="eyebrow">THE COMPETITIVE PICTURE</p>
            <h1>
              {view === "saved"
                ? "Your watchlist"
                : view === "live"
                  ? "Live intelligence"
                  : "Match intelligence"}
              <span className="heading-period">.</span>
            </h1>
            <p>
              {view === "saved"
                ? "Your saved matches, in one place."
                : view === "live"
                  ? "Score-conditioned estimates as the match unfolds."
                  : "The schedule. The probabilities. The context."}
            </p>
          </div>
          <button
            className="update-status"
            onClick={state.retry}
            aria-label="Refresh match data"
          >
            <i
              className={`status-dot ${state.stale || state.phase === "error" ? "stale" : ""}`}
            />
            <span>
              {state.phase === "loading"
                ? "Connecting"
                : state.stale
                  ? "Cached data"
                  : state.phase === "error"
                    ? "Unavailable"
                    : "Updates every minute"}
            </span>
            <Icon name="refresh" />
          </button>
        </div>
        <section className="overview-strip" aria-label="Schedule overview">
          <div>
            <span>On the schedule</span>
            <strong>
              {state.data ? String(matches.length).padStart(2, "0") : "—"}
            </strong>
            <small>upcoming matches</small>
          </div>
          <div>
            <span>Model coverage</span>
            <strong>{state.data ? `${covered}/${matches.length}` : "—"}</strong>
            <small>current estimates</small>
          </div>
          <button
            onClick={() => {
              setView("all");
              reset();
              setLens("close");
              setSort("closest");
            }}
          >
            <span>Close matchups</span>
            <strong>
              {state.data ? String(closeMatches.length).padStart(2, "0") : "—"}
            </strong>
            <small>
              neither side above 60% <Icon name="arrow" />
            </small>
          </button>
          <div>
            <span>Research history</span>
            <strong>
              {preview?.history_count.toLocaleString("en-US") ?? "—"}
            </strong>
            <small>historical series</small>
          </div>
        </section>
        {state.stale && (
          <div className="status-banner" role="status">
            Showing cached data. We’ll retry automatically.
            <button onClick={state.retry}>Retry now</button>
          </div>
        )}
        {storageWarning && (
          <div className="status-banner" role="status">
            Your watchlist is available for this visit, but this browser
            couldn’t save it.
          </div>
        )}
        <div className="workspace-columns">
          <section
            className="board-panel"
            aria-label={
              view === "live" ? "Live match intelligence" : "Match forecasts"
            }
          >
            {view === "live" ? (
              <div className="live-surface">
                <LiveBoard />
              </div>
            ) : (
              <>
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
                  <div className="layout-toggle" aria-label="Board layout">
                    <button
                      aria-label="List view"
                      aria-pressed={layout === "list"}
                      onClick={() => setLayout("list")}
                    >
                      <Icon name="list" />
                    </button>
                    <button
                      aria-label="Grid view"
                      aria-pressed={layout === "grid"}
                      onClick={() => setLayout("grid")}
                    >
                      <Icon name="grid" />
                    </button>
                  </div>
                </div>
                <div className="filter-toolbar">
                  <div className="search-box">
                    <Icon name="search" />
                    <input
                      ref={search}
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search teams or tournaments"
                      aria-label="Search matches"
                    />
                    {query ? (
                      <button
                        aria-label="Clear search"
                        onClick={() => setQuery("")}
                      >
                        <Icon name="close" />
                      </button>
                    ) : (
                      <kbd>/</kbd>
                    )}
                  </div>
                  <label className="filter-select">
                    <span className="sr-only">Filter tournament</span>
                    <select
                      value={event}
                      onChange={(e) => setEvent(e.target.value)}
                    >
                      <option value="">All tournaments</option>
                      {events.map((e) => (
                        <option key={e} value={e}>
                          {e}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="filter-select date-select">
                    <span className="sr-only">Filter date</span>
                    <select
                      value={day}
                      onChange={(e) => setDay(e.target.value)}
                    >
                      <option value="">All dates</option>
                      {days.map((d) => (
                        <option key={d} value={d}>
                          {matchTime(
                            matches.find(
                              (m) => easternDay(m.scheduled_at) === d,
                            )!.scheduled_at,
                            true,
                          )}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="board-caption">
                  <span aria-live="polite">
                    {state.data !== null
                      ? `${visible.length} ${visible.length === 1 ? "match" : "matches"}`
                      : "Loading schedule"}
                    {(query || event || day || lens !== "all") && (
                      <button onClick={reset}>
                        Clear filters <Icon name="close" />
                      </button>
                    )}
                  </span>
                  <label>
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
                </div>
                {state.data === null ? (
                  state.phase === "error" ? (
                    <div className="empty-state" role="status">
                      <Icon name="refresh" />
                      <h2>The schedule is unavailable</h2>
                      <p>The data service is taking longer than expected.</p>
                      <button className="primary-button" onClick={state.retry}>
                        Try again
                      </button>
                    </div>
                  ) : (
                    <div aria-busy="true" aria-label="Loading matches">
                      <p className="loading-copy" role="status">
                        Connecting to the data service. We’ll retry
                        automatically.
                      </p>
                      {[1, 2, 3, 4].map((n) => (
                        <div className="skeleton-card" key={n}>
                          <span />
                          <span />
                          <span />
                        </div>
                      ))}
                    </div>
                  )
                ) : visible.length ? (
                  <>
                    {layout === "list" && (
                      <div className="list-heading" aria-hidden="true">
                        <span>Schedule · ET</span>
                        <span>Matchup</span>
                        <span>Win probability</span>
                        <span>Tournament</span>
                        <span />
                      </div>
                    )}
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
                  </>
                ) : (
                  <div className="empty-state">
                    <Icon name={view === "saved" ? "star" : "search"} />
                    <h2>
                      {view === "saved" && !savedCount
                        ? "Keep the matches that matter."
                        : "No matches in this view."}
                    </h2>
                    <p>
                      {view === "saved" && !savedCount
                        ? "Save a match with the star to build your watchlist."
                        : "Try another team, tournament or date."}
                    </p>
                    <button
                      className="primary-button"
                      onClick={() => {
                        reset();
                        if (view === "saved") setView("all");
                      }}
                    >
                      Explore all matches
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
          <aside className="insight-rail" aria-label="Schedule context">
            {next && (
              <section className="next-match">
                <div className="rail-heading">
                  <span className="eyebrow">NEXT ON THE SCHEDULE</span>
                  <Icon name="arrow" />
                </div>
                <p className="next-time">
                  {matchTime(next.scheduled_at)} <span>ET</span>
                </p>
                <p className="rail-event">{next.event_name}</p>
                <button
                  className="next-fixture"
                  onClick={() => setSelected(next.id)}
                  aria-label="Explore the next matchup"
                >
                  {[
                    {
                      name: next.team1_name,
                      p: next.current_preview?.team1_win_probability,
                    },
                    {
                      name: next.team2_name,
                      p: next.current_preview
                        ? 1 - next.current_preview.team1_win_probability
                        : undefined,
                    },
                  ].map((t) => (
                    <span className="next-team" key={t.name}>
                      <TeamMark name={t.name} />
                      <span>{t.name}</span>
                      <strong>{percent(t.p)}</strong>
                    </span>
                  ))}
                </button>
                <button
                  className="rail-link"
                  onClick={() => setSelected(next.id)}
                >
                  Explore forecast <Icon name="arrow" />
                </button>
              </section>
            )}
            <section className="model-note">
              <span className="eyebrow">THE MODEL, EXPLAINED</span>
              <div className="model-title">
                <h2>Elo v1</h2>
                <span>RESEARCH</span>
              </div>
              <p>
                Historical results, translated into a probability. Every
                estimate comes with its source and context.
              </p>
              <dl>
                <div>
                  <dt>Starting rating</dt>
                  <dd>1500</dd>
                </div>
                <div>
                  <dt>K-factor</dt>
                  <dd>32</dd>
                </div>
                <div>
                  <dt>Rating scale</dt>
                  <dd>400</dd>
                </div>
              </dl>
              <button className="rail-link" onClick={() => setAbout(true)}>
                Read the methodology <Icon name="arrow" />
              </button>
            </section>
            <p className="rail-disclaimer">
              An estimate, not a certainty.
              <br />
              Current probabilities are research outputs, not verified
              prospective performance.
            </p>
          </aside>
        </div>
        <footer className="board-footer">
          <span>
            12:12 <i /> Independent Valorant research
          </span>
          <a href={REPOSITORY_URL} target="_blank" rel="noreferrer">
            Open source <Icon name="arrow" />
          </a>
        </footer>
      </main>
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
