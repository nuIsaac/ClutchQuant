# Multi-source ingestion and startup recovery

## Scope and access

VLR remains supported by the existing collectors. `app.data_sources` provides an
upcoming-source interface; `app.ingestion.multi_source` reconciles the union and
is called by the existing scheduler. The legacy VLR commands still work.

THESPIKE robots/terms endpoints returned HTTP 403 during implementation on
2026-09-28. No permission to automate collection was established. The THESPIKE
adapter **does not scrape**: it reads a locally supplied authorized JSON export.
Live discovery is blocked until an authorized feed/export is supplied. No
historical THESPIKE backfill runs. Phase A accepts upcoming records only; results,
map stats and player stats require a separately validated authorized adapter.

Provide `THESPIKE_EXPORT_PATH` in the worker environment. Docker workers forward
this variable; place the export in their existing artifacts mount, for example
`/data/artifacts/imports/thespike-upcoming.json`. A host path must be translated
to its container-visible path. The GitHub Actions collector remains VLR-only
until an authorized export is supplied in that runner. Files must be refreshed
within 15 minutes, contain at most 500 records, and be at most 5 MB. Do not merely
touch an old export to satisfy freshness. Example shape (illustrative, not live data):

```json
[
  {
    "external_id": "148759",
    "source_url": "https://www.thespike.gg/valorant/match/example/148759",
    "team1": {"external_id": "111", "name": "Example A"},
    "team2": {"external_id": "222", "name": "Example B"},
    "scheduled_at": "2026-10-01T16:00:00Z",
    "event_name": "Example tournament",
    "stage": "Decider",
    "best_of": 3,
    "status": "scheduled"
  }
]
```

Unsupported or partial optional fields can be null; team IDs/names, source URL,
and an explicit-timezone future start are required. Scores are rejected in this
Phase A export format. Raw export bytes are stored in the existing evidence store.
Receipt and ingestion time, never a caller-provided historical date, establish
availability. Replacing the file reader with an authorized API does not require
changing canonical resolution or the forecast pipeline.

## Database and identity

Migration `c81d930a642f` adds `team_source_identities`, `team_aliases`,
`match_sources`, and `source_issues`. Existing teams, players, matches, maps,
forecasts and IDs remain. VLR identities are backfilled from existing IDs;
legacy first-seen timestamps remain NULL rather than inventing discovery dates.
Downgrade removes only the four new tables: export their contents before doing
so, because their provenance would otherwise be lost.

Run from `apps/api`, with DATABASE_URL explicitly set to the intended target:

```sh
.venv/bin/python -m alembic current
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.ingestion.multi_source --source all --pages 1 --dry-run
.venv/bin/python -m app.ingestion.multi_source --source thespike --dry-run
.venv/bin/python -m app.ingestion.multi_source --source all --pages 1
.venv/bin/python -m app.pipeline --once --demo-cycle --pages 1
```

A dry run rolls back database rows, including teams/issues/mappings; raw evidence
files and PostgreSQL sequence increments may remain. It does not generate
forecasts. Its report includes discovery, created/matched/unresolved counts,
coverage and open issues. No production database was provided for this audit.

Team matching prefers explicit source identity, exact NFKC/case/whitespace/
punctuation-normalized names, then known aliases. Multiple candidates are held
for review. Suffix-only similarity such as PCIFIC / PCIFIC Esports requires an
alias review, not an automatic merge. Different IDs from the same source remain
different identities. No fuzzy or roster inference is used.

After verifying a mapping, an operator may insert a `TeamAlias` using
`app.ingestion.resolution.normalize(alias)` for `normalized_alias`, source
`thespike` or `*`, and the existing canonical team ID. Rerun the affected source.
Mark the corresponding issue's `resolved_at` only after reviewing the result.
Ambiguous match records are preserved separately; merging existing canonical
matches/forecasts is deliberately not automated.

Match resolution checks an unordered canonical team pair, normalized event,
stage when present, format when supplied, and a two-hour schedule window. Without
matching stage information the window narrows to 30 minutes. A different existing
identity from the same source is never collapsed. Multiple candidates produce an
`AMBIGUOUS_MATCH` issue and a separate canonical record. Explicit source identities
are unique, and a transaction-level PostgreSQL advisory lock serializes resolution
across both the new and legacy match ingestion entrypoints.

## Conflicts, forecasts and coverage

VLR owns shared canonical values; THESPIKE owns THESPIKE-only records. Secondary
values stay in source metadata/raw evidence. Meaningful disagreements create
deduplicated `SOURCE_CONFLICT` issues and logs; punctuation/case and schedule
changes of five minutes or less do not create conflict noise. A secondary
observation must agree with canonical fields before entering model history.
Upcoming data cannot erase completed scores. VLR map/player writes account for
reversed source team order.

The existing generator selects canonical scheduled Match IDs and uses the same
availability-gated MatchObservation dataset for all sources. Existing unique
(match_id, source_key) forecasts and append-only history are preserved. No Elo
formula or unvalidated feature was added. Late results are usable only after
actual receipt and ingestion, not at their scheduled match time.

The current research preview still uses the bundled VLR history as a bridge:
resolved teams reuse VLR history; teams/matches without VLR identities use
non-colliding internal keys. This preview remains explicitly UNKNOWN availability
and is not a historical backtest or prospective scoring claim.

`GET /api/v1/data/coverage` returns upcoming/recent completed source coverage,
open issue counts, and scheduled matches without saved forecasts.
`GET /api/v1/data/matches/{id}/sources` returns public source links. Upcoming API
responses also include an additive `sources` list, shown under forecast details.
Source count is not model confidence. Raw issue payloads are intentionally not
served publicly; operators inspect `source_issues` in the database.

One source failure does not block the others or forecasting from fresh existing
evidence. Pipeline runs report PARTIAL for collection failures and one-shot commands exit
nonzero after completing independent work. Issues include
source, operation, external ID, exception class and next-cycle retry behavior.
THESPIKE is explicitly disabled/logged if no export is configured. Existing VLR
network retries remain bounded; 401/403 now stop immediately.

## Startup

The checked-in deployment uses Render Free. The prior page awaited one server
request with an eight-second timeout, then rendered an error without recovery.
There is no ingestion/migration startup hook in FastAPI. Hosting wake-up latency
is consistent with the reported delay, but deployment timings/logs were not
available to prove the exact 20–30 second production duration.

The page now renders immediately and uses a server-side Next.js proxy that keeps
API_URL private and unchanged. The proxy checks readiness and reads database-backed
upcoming forecasts. The client retries after 2, 3, then 5 seconds, up to a total
45-second deadline including request time. Each proxy attempt has an eight-second
budget. Unmount cancels requests; refreshes are serialized and run every minute.
No new external ingestion occurs in this upcoming request path. The existing,
separate live-score cache remains unchanged.

- Loading: “ClutchQuant is loading match data…” with automatic retry copy.
- Success: existing matches and forecast interface.
- Empty: “No upcoming matches in this category.” only after successful decoding.
- Exhausted recovery: “Couldn't load match data.” with Retry.
- Failed refresh: retain in-memory data and show a cached-data notice; retry later.

`/health` and `/api/v1/health` report process liveness. `/ready` and
`/api/v1/ready` check database connectivity and the exact migration head. Expected
unavailability returns HTTP 503 with structured `status: starting` and
`Retry-After: 5`, not HTTP 500. Database connection/pool waits are bounded. There
is no model initialization phase to claim as loading, nor should an empty upcoming
table make readiness fail. Render's wake-up behavior itself was not changed.

## Missing-match diagnosis

1. Check configured adapters and discovery counts; THESPIKE disabled is not zero coverage.
2. Check external IDs in source identity tables.
3. Check unresolved-team/ambiguous-match issues; verify aliases.
4. Inspect canonical match status, time, participants and source metadata.
5. Check fresh schedule observations and forecast output; missing history is separate from source coverage.
6. Inspect the upcoming API response and the frontend readiness/retry state.

Run backend tests with an isolated `TEST_DATABASE_URL`, plus `npm test`,
`npm run lint`, `npm run typecheck` and `npm run build` in `apps/web`.

Production integration now includes `/api/v1/data/health` and atomic RLS/runtime-role grants for new tables. See [the measured production integration report](production-integration-report.md).
