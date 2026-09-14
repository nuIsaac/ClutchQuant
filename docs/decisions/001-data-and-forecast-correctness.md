# Data and forecast correctness

Status: implemented and migration `f0a4c2d8e613` applied to the local application
database on 2026-09-14. The later observation/provenance migration is also applied.
This decision records Milestone 1; see [decision 002](002-observation-time-research.md)
for subsequent append-only enforcement, authentication gating, and evaluation work.

## Why this change exists

VLR records can contain non-decisive scores, missing identities, and changed
participants. Those records must not silently become supervised outcomes or
forecasts for a different matchup. These rules concern data eligibility and
forecast interpretation; Elo v1's formula, initial rating, K factor, and source
key remain unchanged.

## Result eligibility

`app.match_eligibility` owns policy `decisive-v1`. A series is eligible only when
its status is completed, both scores exist and are nonnegative, the scores
differ, the teams differ, and a scheduled start exists. The first failing check
provides one reason: `not_completed`, `missing_score`, `negative_score`,
`tied_score`, `same_team`, or `missing_start_time`.

Backtesting, current Elo training, and forecast scoring share this expression.
Ingestion does not delete or rewrite records to make them eligible. A reason
such as `not_completed` also describes ordinary scheduled matches; it is not
necessarily a data error. The policy does not infer series format, forfeits,
actual start time, or result availability from the score.

From `apps/api`, inspect the current records with:

```powershell
.venv/Scripts/python.exe -m app.research.audit_matches
```

The command reads the database and prints JSON with the policy version, counts,
and the internal/VLR IDs and first exclusion reason for every excluded match.
It does not create an immutable dataset snapshot or historical audit ledger.

History is ordered by scheduled start, then internal match ID. The latter makes
equal timestamps deterministic; it does not prove that another result was known
at prediction time. Forecast generation additionally excludes completed records
whose scheduled start is at or after the run's training cutoff, and checks each
upcoming deadline again before constructing its forecast.

The old backtest omitted the completed-status requirement and had no explicit
tie-break ordering. These corrections can change results. Previously reported
metrics have not been reproduced or replaced by this change. Full historical
result-availability handling and reproducible evaluation are the next milestone;
the current chronological backtest must not be described as proof of complete
leakage safety.

## Forecast identity and submission

Stored forecasts remain in the original team order. Scoring compares participant
IDs and reverses result scores when the same two teams have swapped positions.
The score response's teams, probability, outcome, and score fields therefore all
follow the forecast snapshot. If an opponent changes, the forecast stays in the
database and unscored listing, but is excluded from scoring.

The dashboard similarly complements the probability for reversed team order. It
hides the old free-text rationale in that case because ordered rating text cannot
be safely reinterpreted. Changed or unresolved participants receive no displayed
probability or stale rationale.

`POST /api/v1/forecasts` accepts only `source_type: human` and keys matching
`human:[A-Za-z0-9][A-Za-z0-9_.:-]*`. Model and market jobs use internal database
writes. Attempts to submit `model:elo:v1` through the public endpoint, including
under a human source type, fail validation. Existing stored sources are readable
and scoreable. This is an intentional API restriction; callers that previously
posted model/market forecasts must use an internal job.

This does not authenticate human identities. Public human submissions still
require an authentication/authorization design before production exposure.
Forecasts have explicit application submission timestamps and deadline snapshots.
There is still no update/delete endpoint, and an existing match/source forecast
is never silently refreshed. Database-level append-only enforcement and revised
forecasts for replacement opponents are not implemented here.

## Entity identity and migration

Players with missing/nonpositive/noninteger VLR IDs or blank/missing names cause
the ingestion transaction to fail rather than assigning an existing null-ID
player. Existing unknown records are preserved and require explicit review;
this change cannot identify records previously conflated by ingestion.

Team identity is the VLR ID, not its display name. Migration `f0a4c2d8e613` removes
only `teams_name_key`; it preserves all rows and VLR-ID uniqueness. Apply it from
`apps/api` using the configured application database:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
```

Downgrade restores the name constraint. If duplicate names have since been
ingested, PostgreSQL refuses the downgrade; no rows are automatically removed,
merged, or renamed. Review those identities before attempting that rollback.

## Verification

Backend tests cover eligibility reasons and preservation, prediction before
updates, deterministic ordering, training cutoffs, deadlines crossed during a
run, source restrictions, reordered/replaced participants, and entity identity.

```powershell
# From apps/api
.venv/Scripts/python.exe -m pytest -q
```

PostgreSQL tests are opt-in via `TEST_DATABASE_URL`. Use a PostgreSQL database
whose role can create schemas. Each test creates a UUID schema, explicitly sets
its search path, runs real migrations, rolls back its transaction, and removes
only its owned schema. They cover upgrading existing records, duplicate team
names, retained VLR uniqueness, and forecast checks/foreign keys. They never run
migrations against application tables. Without the variable, these tests skip.

```powershell
# After setting TEST_DATABASE_URL, from apps/api
.venv/Scripts/python.exe -m pytest tests/test_postgres_contract.py -q

# From apps/web; tests require Node 22.18+
npm test
npm run lint
npm run build
```
