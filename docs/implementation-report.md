# Multi-source and startup engineering report

Status: implemented and validated locally; **live THESPIKE collection and production rollout remain blocked/not performed**. Repository: `/home/isaac/Projects/ClutchQuant`.

## What changed

- `app/data_sources/{base,vlr,thespike}.py`: upcoming adapter interface, existing VLR parser reuse, authorized THESPIKE export reader.
- `app/ingestion/{resolution,multi_source}.py`: canonical reconciliation, isolated source failures, dry-run CLI, coverage reporting.
- `app/ingestion/vlr.py` and `vlr_stats.py`: legacy ingestion delegates match persistence to the resolver; reversed source order is handled for map/player writes; restricted requests stop immediately.
- `app/models.py` and migration `c81d930a642f`: additive provenance/mapping/review tables.
- `app/pipeline.py`: upcoming union and partial-failure handling while continuing independent forecasting.
- `app/research/preview.py`: bridge non-VLR entities into the existing current research preview without changing Elo.
- `app/routers/{matches,sources}.py`, `schemas.py`: additive source metadata and coverage endpoints.
- `app/main.py`, `database.py`: structured readiness and bounded database connection/pool waits.
- Frontend `page.tsx`, `/api/upcoming`, `startup.ts`, `use-upcoming.ts`, `upcoming.ts`, `market-board.tsx`: automatic cold-start recovery, retained data on failed refresh, and inspectable source links.
- Backend/frontend tests, Compose worker configuration, environment examples, README and [runbook](multi-source.md).

## Database changes

Four new tables: `match_sources`, `team_source_identities`, `team_aliases`, `source_issues`. Unique source/external-ID constraints and foreign keys retain canonical relationships. Existing VLR mappings are backfilled; unknown discovery timestamps stay NULL. No existing rows or IDs are deleted/reassigned by the migration. The migration chain, preservation and downgrade were tested on disposable PostgreSQL 16. Production's 30,000+ rows were not accessed.

## Data flow

VLR parser / authorized THESPIKE export → team resolution → canonical match resolution → source attachment and accepted availability observations → existing forecast generator → database-backed API → frontend. Existing VLR backfill entrypoints remain available. Source adapters may omit unsupported capabilities; THESPIKE currently supports Phase A schedules only.

## Duplicate protection

Explicit source identity wins. Team names normalize Unicode/case/whitespace/punctuation; aliases handle verified naming differences. Suffix similarity and ambiguous names require review. Matching uses unordered teams, event, stage/format when available, and a bounded schedule window. Same-source distinct match IDs are not merged. Ambiguous matches remain separate with review issues. PostgreSQL advisory locking serializes resolution; forecast uniqueness remains enforced by the existing database constraint.

## Source conflicts

VLR remains authoritative for shared records; THESPIKE controls THESPIKE-only records. Source metadata and raw evidence retain secondary values. Significant conflicts produce deduplicated issues/logs. Conflicting secondary observations do not enter feature history. Source count never modifies model confidence.

## Forecast integration

The existing generator already consumes canonical Match IDs. Tests now demonstrate a THESPIKE-only match receiving a prospective forecast, attaching a later VLR identity without duplication, and rejecting future/late-imported information from earlier snapshots. No Elo formula, map feature or arbitrary head-to-head feature was added. Current research previews retain their UNKNOWN-availability label and are not prospective evaluation evidence.

## Startup fix

Verified code-level cause: one eight-second server-side request produced a permanent page error; there was no retry. Render Free is the configured host, making wake-up latency a plausible contributor. Exact production cold-start duration was not measured because deployment logs/access were not supplied. FastAPI has no ingestion/migration initialization hook to remove.

The shell renders immediately; a same-origin proxy checks readiness and fetches matches while keeping API_URL server-side. Client retries use 2/3/5-second backoff within a total 45-second window, with an eight-second proxy request budget. Database connection/pool waits are bounded. Hosting plan and environment targets were not changed.

## UX behavior

| State | Behavior |
|---|---|
| Normal load | Brief loading state, then existing match interface |
| Cold start | “ClutchQuant is loading match data…”; automatic bounded retries |
| Empty success | “No upcoming matches in this category.” |
| Persistent failure | “Couldn't load match data.” and Retry |
| Refresh failure | Existing in-memory data remains with cached-data notice |

## Validation results

[Live VLR dry-run report](validation/live-vlr-dry-run.json): one listing page, empty disposable database, **8 forecastable records**, 8 proposed canonical matches, 0 unresolved teams, 0 conflicts, 0 failures. All database changes rolled back. Forecasts generated: 0 (discovery dry run only). THESPIKE live discovery: **not available**, not a measured zero. Production overlap is unmeasured.

[Synthetic union report](validation/source-union.json): VLR 2, THESPIKE 2, shared 1, VLR-only 1, THESPIKE-only 1 → **3 canonical matches**. Ambiguous 0, conflicts 0, forecasts generated 3, duplicate forecasts on repeat 0. These are fixture counts, not claims about today's real coverage. Reproduce with `scripts/validate_source_union.py` and an explicit disposable TEST_DATABASE_URL.

[Browser recovery report](validation/startup-browser.json): headless Chrome against the production frontend build with controlled API responses. Recovery after 20.65 seconds / 6 requests; persistent outage error after 45.20 seconds / 10 requests; Retry recovered to the successful empty state. Startup screenshot was visually inspected. The PCIFIC/Fear Never Ends scenario is covered as a source-only architectural fixture, not claimed as a verified live THESPIKE match.

## Tests

- Backend: **194 passed**, including actual PostgreSQL migration, foreign-key, append-only, forecast, temporal-availability and reconciliation tests.
- Frontend: **24 passed**, including cold-start, permanent outage, cancellation, empty success and cached-data retention tests.
- Frontend ESLint, TypeScript and production build: passed.
- Browser cold-start / permanent outage / Retry scenarios: passed.
- Demo deployment configuration checks: passed.
- Docker deployment smoke: could not run (`docker` executable unavailable).

One pre-existing test was updated because it asserted that collection failure must stop all forecasting; the requested behavior now asserts partial failure while allowing independent forecasts.

## Remaining limitations

1. THESPIKE returned HTTP 403 for robots/terms; no authorized feed/export was supplied. Scraping is disabled. End-to-end live multi-source coverage is therefore not complete.
2. THESPIKE recent-result, historical, map and player collection are deferred. The canonical resolver/observation pipeline supports temporally correct imported results, demonstrated in PostgreSQL tests, but the Phase A export reader intentionally rejects them.
3. No production database migration, historical backfill, push or deployment occurred. Production coverage, the original live match and exact hosting cold-start latency remain unverified.
4. Alias and ambiguity review is an operator/database workflow, not a new admin UI. Fuzzy/roster matching and automated canonical record merging are deliberately absent.
5. The existing separate VLR live-score cache remains request-triggered; this change adds no external collection to upcoming forecast requests.
6. Docker container execution remains untested locally; the repository's CI container checks remain available.
