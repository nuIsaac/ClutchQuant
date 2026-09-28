# Existing-production integration — 2026-09-28

**Result:** integration is validated locally, including live VLR persistence and forecasting. **The existing production deployment was not updated:** this session has no authenticated GitHub push access, provider login, or production database connection. No production migration or write was attempted without a backup and administrator access.

## Existing deployment and exact comparison

Public GitHub deployment records identify commit `3e5aa9bb6bb5804879348affc163d7f8d81d7f73` as the existing successful Vercel and Render deployments. The remote default branch was also at that commit when checked.

- Frontend: `https://clutch-quant.vercel.app` on Vercel.
- Backend: `https://clutchquant-api-demo.onrender.com` on Render.
- Database/evidence: existing Supabase PostgreSQL and private Storage configuration.
- Collection: existing GitHub Actions `Prospective demo cycle`, every three hours; unchanged schedule and environment targets.

Read-only production checks returned HTTP 200 for health, readiness, and upcoming forecasts. Readiness reported migration **`b72c904e1a36`**. The API returned **8 upcoming matches, 8 saved forecasts and 8 current previews**; the production browser rendered them with no observed console warnings/errors. New `/api/v1/data/coverage` and `/api/v1/data/health` return 404 there because the integration has not deployed. [Captured baseline](validation/production-baseline.json).

The diff is confined to additive provenance schema, reconciliation and source adapters, forecast integration/counters, additive API responses and health summaries, frontend cold-start recovery, worker configuration, tests and documentation. Elo v1 and model features are unchanged. No hosting setup, service tier, production URL or schedule was changed.

## Integration fixes in this pass

1. **Production permissions:** the new-table migration enables row-level security, revokes public/anonymous/authenticated access, and grants appropriate access only to existing `cq_demo_api` / `cq_demo_worker` roles. It also preserves the existing optional self-hosted `cq_app` role. No roles or credentials are created by this migration. The existing Supabase permission script now includes all four new tables.
2. **Lightweight health:** `/api/v1/data/health` summarizes existing `pipeline_runs` receipts. No monitoring service, dashboard database, or infrastructure was added.
3. **Counters/logs:** source summaries distinguish fetched, forecastable, not-forecastable, parse/persistence failures, new/matched canonicals, source mappings and unresolved records. Forecast generation reports duplicate attempts prevented. Pipeline start/end and source summaries are logged without per-success-row spam.
4. **Malformed listings:** missing VLR listing markup now reports a collection failure rather than a successful empty feed. A malformed individual match does not discard other valid matches.
5. **Validation:** added role/security, historical relationship, data-health sanitization, malformed-source and disabled-THESPIKE tests, plus a reproducible isolated live integration script.
6. Preserved the earlier implementation report as [historical documentation](implementation-report-before-multi-source.md).

## Database migration and historical integrity

Migration `c81d930a642f` adds only `match_sources`, `team_source_identities`, `team_aliases`, and `source_issues`, plus their indexes, source uniqueness, foreign keys and access policies. It backfills VLR mappings without fabricating original discovery timestamps. Existing matches, maps, player stats, model runs, observations and forecasts are not rewritten by the migration.

The integration script imported the **30,299-match bundled history** into a new disposable PostgreSQL schema at the currently deployed migration head. It applied the new migration twice, compared row counts and complete row fingerprints, and ran Alembic's schema comparison.

| Check | Result |
|---|---|
| Historical matches before/after migration | 30,299 / 30,299 |
| Distinct canonical IDs before/after | 30,299 / 30,299 |
| Backfilled VLR match mappings | 30,299 |
| Complete historical match row fingerprint | Identical after migration and both live ingestion runs |
| Orphaned foreign keys | 0 |
| Duplicate forecast groups | 0 |
| Potential duplicate match groups | 0 |
| Alembic schema comparison | No new upgrade operations detected |

The snapshot contains **no map/player-stat/forecast rows**; those relationships were separately tested with populated PostgreSQL fixtures, including historical model-run/forecast references and applying the migration twice. Existing append-only and forecast uniqueness tests also pass. This is not a production database copy, and it does **not** verify inaccessible production row counts or claim that a production backup exists.

## Real VLR end-to-end result

[Full measured report](validation/live-vlr-integration.json). Each run used real current VLR responses and persisted data through the new resolver, then ran the existing prospective forecast generator and queried FastAPI.

| Metric | First run | Second live ingestion run |
|---|---:|---:|
| Match detail pages fetched | 30 | 30 |
| Forecastable records parsed | 8 | 8 |
| Not yet forecastable | 22 | 22 |
| Canonical matches created | 8 | 0 |
| Existing canonicals matched | 0 | 8 |
| Match mappings created | 8 | 0 |
| Team mappings created | 0 (already backfilled) | 0 |
| Unresolved / conflicts / parse / persistence failures | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Forecasts created | 8 | 0 |
| Forecasts skipped | 0 | 8 |
| Duplicate forecasts prevented | 0 | 8 |
| Total processing seconds | 35.556 | 34.716 |

The final API returned 8 matches, each with source provenance and saved forecasts. Final match count was 30,307, with all original historical IDs and rows unchanged. The updated frontend rendered these persisted matches and provenance links.

The real production read-only API also works, but **updated VLR production ingestion was not run**, because no production write credentials were available.

## Observability and failure behavior

`GET /api/v1/data/health` exposes sanitized datasource status, last attempted/successful collection time, data age, per-source counters, forecast creation/skips/duplicate prevention, oldest/latest match times and existing coverage/conflict totals. It reads at most the last 100 pipeline receipts; source health becomes stale after four hours, appropriate for the existing three-hour scheduler. It contains no raw issue payloads, secret configuration, artifact keys or exception text.

`GET /api/v1/data/coverage` remains the detailed aggregate coverage endpoint. Source provenance remains inspectable in the match API/UI. Operational summaries are intentionally safe for public read access; detailed source issue payloads remain database-only behind role permissions.

THESPIKE is optional and disabled when no authorized export is configured. Disabled status is not an application error and does not degrade successful VLR operation. The adapter remains ready for an authorized export; an authorized API can replace its retrieval boundary without changing canonical resolution or forecast interfaces. No THESPIKE request or restriction bypass was attempted in this pass.

When VLR fails, existing database records remain available. A fresh page retries up to 45 seconds before showing an error. A loaded page retains matches after failed refresh and displays its cached-data notice. Provider disagreements remain logged/reviewable rather than silently entering model history.

## Model baseline

Frozen Elo v1 on the unchanged bundled snapshot, in chronological order:

- Matches: **30,299**, from 2020-04-25 through 2026-09-15.
- Accuracy: **0.6450707944**.
- Brier score: **0.2200526323**.
- Log loss: **0.6300651361**.

**UNKNOWN historical availability: these are retrospective diagnostics, not leakage-certified prospective performance or grounds to promote a model.** The eight new prospective forecasts use existing availability safeguards; importing old history does not invent result availability. Production's current preview includes additional recent results, so its preview probabilities need not equal this older snapshot's values. No performance change is claimed.

## Validation commands and outcomes

From `apps/api`, with an explicitly isolated PostgreSQL `TEST_DATABASE_URL`:

- `.venv/bin/python -m pytest -q`: **200 passed, 0 skipped**.
- `.venv/bin/python -m compileall -q app migrations ../../scripts`: passed.
- `PYTHONPATH=. .venv/bin/python ../../scripts/validate_production_integration.py --report /tmp/cq-live-integration.json --keep-schema`: passed, real-source results above.
- Migration upgrade twice and `alembic check`: passed in the validation schema.

From `apps/web`:

- `npm test`: **24 passed**.
- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `npm run build`: passed.

Deployment configuration contract and YAML parsing passed. Docker execution is blocked: this host has no `docker`, `dockerd` or `podman` executable and no system/user Docker socket. No new Docker infrastructure was installed.

Browser checks against the production frontend build connected to the disposable database: normal live VLR success, no runtime console warnings/errors, and automatic recovery after a controlled 20-second delayed API restart were observed. A sustained outage produced the error/Retry state in a fresh tab while a previously loaded tab retained the real matches and displayed its cached-data notice. After the API returned, the fresh tab recovered through automatic background retry and the cached tab automatically cleared its stale notice. Empty-category rendering and visible VLR source provenance also passed. See [browser checks](validation/integration-browser.json).

## Deployment access and rollout status

The clean prior implementation checkpoint is commit `22885d1` on branch `integration/multi-source-production`. No force push or history rewrite occurred.

Checkpoint `22885d1` and integration commit `8c5b3b7` were created locally. Both a dry run and the actual `git push -u origin integration/multi-source-production` failed with `could not read Username for 'https://github.com': terminal prompts disabled`. No Git credential helper, GitHub token, SSH identity, cloud CLI credential file or production DATABASE_URL is available. Vercel and Render dashboards both opened at their login screens. The existing public deployment is healthy and remains untouched.

**The remaining rollout blocker is authenticated access to the existing GitHub/provider/database environment.** THESPIKE authorization is deliberately not a blocker for this VLR-backed rollout.

## Safe existing-process rollout and rollback

Once the existing authorized environment is available, the repository's existing process applies: pause scheduled collection, record current deployment/migration, export the application database and complete private evidence bucket to protected storage, verify recovery material, then apply the additive migration with the administrator connection. Recheck counts/fingerprints/foreign keys and runtime role grants before deploying the existing Render/Vercel projects and dispatching the existing collection workflow. No new infrastructure is required.

Do not push/merge directly to the auto-deployed production branch before that migration/backup gate. This integration stays on its own branch. After release, inspect health/coverage and frozen forecasts, then resume the existing schedule.

For code rollback, use the prior Render/Vercel deployment at `3e5aa9b`. The additive schema can remain: old code ignores the new tables. Do not drop provenance or overwrite append-only records as an automatic rollback. If database restore is ever required, restore the verified application data and complete artifact archive into a separate recovery target, verify them, and deliberately switch the existing environment configuration. No production rollback or restore was needed/performed here.

Next milestone: complete that authenticated production rollout and verify the first scheduled VLR cycle under the new health counters. Model redesign and THESPIKE live activation remain separate future work.
