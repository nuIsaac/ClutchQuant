# Live probability v1

The public UI uses the current research prior and score-conditioned live estimates.
The internal forecast, observation and scoring system is unchanged. Live estimates
never enter its tables or performance metrics. No schema or privilege changes.

## Data inspected

Local Postgres contained 591 completed maps from 237 series, eight map names, dated
2026-07-26 through 2026-08-29. It has no round-state training table or timestamped
round-by-round snapshots. Completed-map side totals are not current-side evidence.

`python -m app.research.calibrate_live` performs a read-only diagnostic. Elo features
are computed before each series in scheduled-time order, with equal start times
grouped. Training uses 482 maps; the later holdout uses 109. A single fitted
round-log-odds scale gave holdout log loss 0.680 versus 0.699 for Elo-as-map-prior
and 0.693 for neutral. These are map diagnostics with unknown original availability,
not live-model validation. Inputs, cutoff, fitted coefficient and exact metrics
are in `app/research/live_calibration.json`.

The fitted candidate is not deployed: this narrow map sample cannot establish
in-round calibration, and substituting it would change the existing series prior.
No supervised live model is trained on invented snapshots.

## Probability calculation

The deployed model is `live:markov:v1`:

1. Reuse Elo v1 research ratings from results scheduled before the match start.
   Exclude all currently live matches from training. This remains a research prior,
   not a claim of historically observed availability.
2. Numerically invert the BO1/BO3/BO5 series probability to find a common map prior.
3. Invert the first-to-13 map probability to infer a constant per-round probability.
   There is no invented fitted coefficient; at 0-0 the series estimate equals Elo.
4. Dynamic programming conditions on the actual map score. Regulation switches
   sides after 12 rounds; overtime alternates sides and requires a two-round lead.
   The engine supports explicit side-specific scenario inputs, but the source route
   uses equal side probabilities because reliable side effects were not estimated.
5. At overtime deuce, if the two round probabilities are x and y, eventual victory
   is xy / (xy + (1-x)(1-y)). This closes the infinite overtime recursion exactly.
6. A second DP combines the current map probability with the remaining maps to
   calculate the chance of reaching the required series wins.

Independent rounds and exchangeable maps are simplifying assumptions. Economy,
rosters, pistol rounds, map-specific and side-specific advantages are not modeled.
Draw formats and nonstandard scoring are unsupported. Extreme live probabilities
are model estimates, not empirically calibrated confidence statements.

## Source and cadence

`app/ingestion/vlr_live.py` reuses VLR identities and the existing match-page HTML
structure. Only explicit `Live` listing entries are fetched. A detail page must
confirm live/final status, BO format, team identities and series scores. Round
scores are accepted only from the expected map number and matching team names.
Missing rounds remain null; series-only estimates are labeled as such.

The inspected listing had no active matches. Completed-page structure was verified;
active round-level integration remains conditional on compatible real source HTML.
No synthetic state is returned by the production API. Parser tests use labeled
synthetic HTML, never database observations.

`GET /api/v1/matches/live` shares one process-local source cache and lock. While
visitors are polling, it checks every 30 seconds with active matches, every five
minutes with none, and waits 60 seconds after source failure. At most four active
detail pages are fetched per refresh, with bounded concurrency and four-second
HTTP timeouts. Partial coverage is explicit. Run one API process in this demo;
multiple replicas require a shared cache before scaling collection.

Next.js proxies through `/api/live`, retaining server-only API configuration. The
browser follows the server cadence and skips hidden-tab requests. There is no
keepalive process or background scraping when nobody uses the feed. Render sleep
and source latency prevent any second-by-second guarantee.

Live receipt timestamps and raw hashes are exposed, but raw bodies and state are
ephemeral, not durable evaluation evidence. Source errors clear live probabilities
rather than presenting stale values. A final state may appear on the last fetch
before the match leaves the live listing; this is not a completed-match archive.

## Verification

Tests cover score bounds, complement symmetry, nonlinear updates, completed states,
BO1/3/5, overtime, side switching, malformed/missing source state, cache behavior
and source outages. Frozen rows and the scheduled collection command are unaffected.
