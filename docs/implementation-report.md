# ClutchQuant implementation report — 2026-09-14

## Current follow-up: prospective operation

This section supersedes the earlier milestone snapshot below. Historical
availability was accepted as unknown; no historical timestamps or model performance
were manufactured. Prospective collection and forecasting are now running locally.

### 1. Completed

- Added versioned retrieval/parse receipts, raw/listing provenance, explicit
  observation timing, and idempotent retry keys. Actual later captures append
  observations; content hashes deduplicate raw bytes.
- Added the prospective freeze protocol: fresh matching schedule evidence, exact
  feature/model/dataset provenance, immutable probability and lock time, and stable
  prospective source keys. Frozen Elo v1 can start with its explicitly labeled
  prior; the first real run instead had 50 observed results available for training.
- Added actual frozen-forecast scoring with integrity checks, participant
  orientation, ineligible-result reasons, and correction/retraction handling.
  Reports are immutable and reproducible; historical experiments/legacy forecasts
  are excluded from prospective metrics. Calibration is withheld below 100 outcomes.
- Added a locked, bounded job cycle; recurring local/container worker; one-shot
  scheduler entry point; immutable job receipts; failure exit status; and worker
  health checks. Added paginated API history and dashboard display.
- Applied tested migration `b72c904e1a36` to the verified local database from
  `a21d7b643f90`. Added nullable observation evidence keys and append-only pipeline
  run receipts. Existing data hashes were unchanged; schema comparison passed.

### 2. Still blocked or limited

Original historical availability remains unknown. Actual prospective outcomes
cannot be produced before matches finish. No model superiority or calibrated
performance is claimed. Cloud credentials/infrastructure, public HTTPS deployment,
production operational alerts, multi-user authentication, and a native S3 adapter
remain future environment/product work. Player/roster features remain unsupported.
Human submissions and legacy generation commands remain outside the verified
prospective model protocol and are excluded from its metrics.
Scheduled start is not independently verified actual start; collector clocks and
capture delays remain limitations. Snapshot/report scans scale with stored history
and should be load-tested before increasing production volume.

### 3. Prospective collection status

The first permitted-network cycle succeeded from `2026-09-14T17:09:28Z` to
`17:12:52Z`: 50 result observations, 17 upcoming observations, 33 non-forecastable
upcoming cards skipped, zero parsing/ingestion failures, and 17 new frozen Elo v1
forecasts. All 17 were pending outcomes. The three prior forecasts remained
unverified legacy records and were preserved. An earlier sandbox proxy connection
failure is recorded as a failed job; the authorized network retry succeeded.

First report: `dc7523d04be031b6958329e415e79d8376e851e88c2d41393bd27a84b1062ec2`.
Rebuilding from its referenced dataset produced the identical hash.

The `clutchquant-worker` Docker container is running against the same database and
artifact directory. It repeats one bounded page per source with a 300-second delay
after each cycle and restarts unless explicitly stopped. Docker/host uptime and
outbound HTTPS are required; no cloud scheduler has been provisioned.

The first production-container cycle also succeeded, finishing at
`2026-09-14T17:16:49Z`: 67 additional observations, **0 new forecasts**, and 17
existing forecasts skipped without mutation. Total observations were **134** at
verification. Docker reported **running / healthy**, and the explicit worker health
command passed. Its report hash is
`2376d9c6f11cbcaf759c0d1921359ab442ac93c299bc9bc6d996793535e33cc7`.

### 4. Current models

| Model | Live prospective state | Verified resolved sample |
| --- | --- | ---: |
| Frozen Elo v1 | 17 saved forecasts, pending outcomes | 0 |
| Elo v2 30/90/180-day candidates | Available behind experimental opt-in; not promoted | 0 |
| Logistic regression / gradient boosting | Require sufficient observed training history | 0 |
| Ensemble | No supporting evidence; not generated or promoted | 0 |

The old diagnostic metrics remain in the historical snapshot below. They are not
combined with the prospective report or presented as prospective performance.

### 5. Validation

- 113 backend tests passed, including real PostgreSQL migrations, idempotency,
  cold-start freeze, delayed scoring, retraction, team reversal/replacement,
  early-start exclusion, collection failure, and overlap prevention.
- 14 frontend tests passed; lint, TypeScript and production build passed.
- Both production images built. Container readiness reported `b72c904e1a36`;
  health, forecasts, upcoming bundles, scoring, and prospective reporting returned
  200. Pagination and honest empty prospective metrics passed. The web rendered
  the recorded history with real data. Production human submission returned 403.
- Two real network-backed pipeline cycles captured evidence and preserved forecasts;
  report reproducibility passed. Temporary HTTP-smoke containers/network were
  removed; the authorized recurring worker remains running.
- `git diff --check` passed. Existing API_URL and frozen `elo.py` remain preserved.

### 6. Deployment readiness

Environment-driven production images, readiness, explicit migrations, shared
artifact storage, local recurring worker, one-shot scheduled tasks, health signals,
and GitHub Actions validation are prepared. The runbook covers RDS/S3/ECR/ECS and
CloudWatch responsibilities. Local containers are tested; there is no public URL
or AWS deployment. GitHub Actions has not run remotely in this session.

### 7. Git state and diff

No stale `index.lock` exists. `.git` has explicit deny ACL entries for sandbox
identities. No permissions/security controls were changed, and no commits or push
were attempted through a workaround. Changes remain uncommitted. Current tracked
diff: **26 files, 659 insertions, 411 deletions**, plus **45 untracked files**.
This includes earlier milestone work; untracked files are omitted by `git diff --stat`.
The runbook includes exact normal-terminal review/add/commit commands.

### 8. Next human actions

Keep Docker Desktop/database/worker running on an awake host to accumulate evidence.
Monitor worker health and collection coverage; verify artifact/database backups.
Review the implementation and make a local Git checkpoint from a normal terminal.
Choose a staging/deployment environment, budget, credentials, and public domain
before cloud provisioning. Wait for real resolved samples before comparing or
promoting models. No additional credentials are needed for the running local worker.

---

## Earlier milestone snapshot (retained for audit; superseded above)

The implementation and local validation are complete for the available evidence.
The project is not finished: trustworthy historical model comparison is BLOCKED,
and public deployment has not occurred.

## 1. Implemented work

Completed data/forecast correctness work and applied its migration. Added raw
response capture, immutable snapshots, observation-time replay, correction handling,
calibration/segmented reports, experimental models, persistent run provenance,
append-only forecast protection, a multi-model dashboard, and deployment preparation.
Preserved raw historical rows, existing forecasts, frozen Elo v1, and API_URL.

## 2. Architecture

Small Python modules separate eligibility, artifacts, observation capture, dataset
export, online model state/features, evaluation, and generation. SQLAlchemy remains
the persistence layer; scikit-learn implements the two supervised models. Next.js
loads bounded upcoming-match/forecast bundles through FastAPI. It distinguishes
missing forecasts, experimental versions, errors, and empty schedules. Existing
single-model APIs remain available. See decisions 001/002 and the runbook.

## 3. Database migrations

Verified local Docker `clutchquant-postgres` (PostgreSQL 17.11), localhost:5432,
database/role `clutchquant`, schema `public`. The starting revision was
`eaf7597a5438`. Applied `f0a4c2d8e613` to remove only team display-name uniqueness;
VLR identity uniqueness remains. Then applied `a21d7b643f90` for observations,
model runs, nullable forecast provenance, and append-only triggers.

Final revision: `a21d7b643f90 (head)`. Alembic schema comparison reports no pending
operations. Existing-table content hashes and counts were preserved (new nullable
provenance column excluded from the old-column hash): 30,801 matches, 5,366 teams,
548 players, 591 maps, 5,910 player/map statistics, and 3 forecasts. No historical
observations or model runs were invented. Controlled writes were rolled back;
constraints and application reads passed. Production-container writes without an
operator token returned 403 without inserting a forecast.

## 4. Final model results

| Model / protocol | Matches | Accuracy | Brier | Log loss | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| Elo v1 legacy scheduled-order diagnostic | 30,245 | 0.645297 | 0.219984 | 0.629922 | NOT_LEAKAGE_SAFE |
| Elo v1 observed-time protocol | 0 | — | — | — | BLOCKED |
| Elo v2 decay 30 days | 0 | — | — | — | BLOCKED |
| Elo v2 decay 90 days | 0 | — | — | — | BLOCKED |
| Elo v2 decay 180 days | 0 | — | — | — | BLOCKED |
| Logistic regression v1 | 0 | — | — | — | BLOCKED |
| Histogram gradient boosting v1 | 0 | — | — | — | BLOCKED |
| Equal-weight ensemble candidate | 0 | — | — | — | NOT_PROMOTED / BLOCKED |

The diagnostic rated 5,286 teams and reproduces the historical reference figures.
It is not a held-out observed-time estimate and cannot validate a new model.
Strict evaluation excludes 30,245 records for unknown result availability, 242 for
missing scores, 26 for non-completed status, and 288 for tied scores. Raw records
remain present. No supported pre-match schedule/result observation pairs exist.

## 5. Elo v1 versus Elo v2

V1 formula/parameters are unchanged. V2 candidates and causal replay are tested,
but no empirical advantage can be measured from this database's evidence. No
half-life was selected; the three-month hypothesis remains unvalidated. Decay
uses elapsed time since observed results, an explicit proxy for inactivity.

## 6. Logistic regression and gradient boosting

Implemented fixed configurations, scaled logistic features, deterministic seeds,
monthly chronological refitting, minimum training size, and missingness indicators.
Synthetic tests validate operation and leakage boundaries, not real performance.
Both models have zero supported real evaluation predictions and remain experimental.

## 7. Ensemble

Implemented an interpretable equal-probability candidate and a common-cohort
probability-quality review gate. The current report does not support it. No
ensemble forecasts were inserted and no model was promoted. Existing individual
forecasts remain readable. Strict generation correctly returned BLOCKED/created 0.

## 8. Calibration

Reports include ten probability bins and expected calibration error, with recent,
monthly, and event segmentation. Legacy diagnostic ECE is 0.045565; this is only a
descriptive statistic under the legacy protocol. Strict calibration is UNKNOWN
because the supported sample is empty. No calibration correction was fitted.

## 9. Validation

- Backend: 96 tests passed, including real PostgreSQL migration/constraint tests,
  causal correction replay, future perturbation, artifact integrity, and generation.
- Frontend: 12 tests passed; lint, TypeScript, and production build passed.
- Final Linux API and web images built successfully. API readiness and health,
  upcoming forecast bundles, forecasts, and scoring returned 200. Web rendered 200.
  Non-root artifact read/write and code identity without Git passed. Temporary
  smoke containers and their network were removed.
- npm lock metadata was regenerated for Linux after a targeted js-yaml 4.3.2
  security update exposed optional dependency mismatch; lock audit found zero
  vulnerabilities. This is not a comprehensive infrastructure/security audit.
- Alembic current/head and schema comparison passed. `git diff --check` passed
  (Git reports Windows line-ending normalization notices).
- Repeated evaluation of the same immutable dataset produced the identical report
  SHA-256. No remote GitHub Actions or AWS deployment was executed.

Dataset SHA-256:
`6ed69a25b6aea25b78ae15eb98c285b9edfe70f91c76603c2941b9229a8842a4`

Report SHA-256:
`d65bee65ed8a5e3dfef3ecc3476fdf92f2ccc4b1729bff22ad9db3c8f3a3a2fa`

Snapshot as-of: `2026-09-14T16:35:32.182302+00:00`. Validation starts
`2025-01-01T00:00:00Z`; test starts `2026-01-01T00:00:00Z`. Artifacts are in
`apps/api/artifacts/datasets/` and `reports/`, ignored by Git; back them up separately.

## 10. Known limitations

Scheduled time is not actual start. Collector timestamps depend on clock quality
and capture delays. Historical normalized data may contain unresolved identity
problems that cannot be automatically repaired. Replay uses observed scheduled
deadlines; live jobs run at their actual generation time, so forecast horizons
need explicit future evaluation. No supported roster/map/patch/region/tier feature
history exists. Ensemble gates are not statistical proof. Filesystem artifacts
need durable storage/backup; S3 integration is not implemented. Operator-token
gating is not multi-user authentication. Database-owner privileges can bypass
append-only protections. A benign Node module-type warning appears in TS unit tests.

## 11. UNKNOWN / BLOCKED

Historical availability and strict real performance for every model remain
UNKNOWN/BLOCKED. The next evidence source is prospective schedule/result collection
or authoritative historical availability records; fetching old pages now cannot
recover that history. Real experimental/ensemble generation is deliberately blocked.
No live source collection, public URL, AWS provisioning, operational scheduler,
CloudWatch alerts, load test, or production deployment was completed.

## 12. Git state and diff

Git checkpoint creation failed because `.git/index.lock` permission was denied.
No workaround, commit, or push was performed. Work remains uncommitted for review.
The following tracked-file diff includes the initial Milestone 1 working tree;
untracked files are not included in this Git statistic.

```text
 .gitignore                                      |   2 +
 README.md                                       |  23 +-
 apps/api/app/database.py                        |   6 +-
 apps/api/app/ingestion/vlr.py                   |  31 ++-
 apps/api/app/ingestion/vlr_stats.py             |  40 ++-
 apps/api/app/main.py                            |  26 +-
 apps/api/app/models.py                          |  26 +-
 apps/api/app/research/backtest_elo.py           |  19 +-
 apps/api/app/research/generate_elo_forecasts.py |  30 +-
 apps/api/app/routers/forecasts.py               |  61 +++-
 apps/api/app/routers/matches.py                 |  20 +-
 apps/api/app/schemas.py                         |  16 +-
 apps/api/app/scoring.py                         |   5 +-
 apps/api/migrations/env.py                      |  16 +-
 apps/api/requirements.txt                       |   5 +-
 apps/api/tests/test_forecast_api.py             | 139 +++++++++-
 apps/api/tests/test_scoring.py                  |   5 +-
 apps/web/README.md                              |   8 +
 apps/web/next.config.ts                         |   2 +-
 apps/web/package-lock.json                      | 122 ++++++--
 apps/web/package.json                           |   4 +-
 apps/web/src/app/globals.css                    |   4 +-
 apps/web/src/app/layout.tsx                     |  17 +-
 apps/web/src/app/page.tsx                       | 354 +++++-------------------
 24 files changed, 578 insertions(+), 403 deletions(-)
```

There are additionally 37 new untracked files, including both migrations, research
modules/tests, frontend utilities/tests, Dockerfiles, CI, configuration, and docs.
Frozen `apps/api/app/research/elo.py` has no diff.

## 13. Recommended next work

Begin monitored prospective observation collection and preserve artifacts before
claiming model improvements. Review the evidence protocol and forecast horizons,
then pre-register sufficient validation/holdout windows. For deployment, follow
the runbook: staging database and restore test, explicit migration job, durable
artifact storage/S3 backup, ECR images, HTTPS container services, secrets, logs,
alerts, scheduler, and deployment CI. Keep human writes disabled until the intended
authentication design is implemented. Public usability still needs staging and
production verification in the selected environment.
