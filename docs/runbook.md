# Operating ClutchQuant

## Prospective operation (current workflow)

This session started the local Docker container `clutchquant-worker`, using the
existing `apps/api/artifacts` directory and local database, with restart policy
`unless-stopped`. It publishes no ports. Keep Docker Desktop and the host awake.

```powershell
docker logs --tail 50 clutchquant-worker
docker inspect --format '{{.State.Status}} {{.State.Health.Status}}' clutchquant-worker
docker exec clutchquant-worker python -m app.pipeline --health
docker stop clutchquant-worker
docker start clutchquant-worker
```

Stopping is intentional and prevents further collection; restarting resumes future
cycles without rewriting old forecasts. Do not start a second manual worker while
this one is active. The database advisory lock prevents overlap but does not make
duplicate deployments useful. Rebuild/recreate the worker after code upgrades;
its container image does not automatically follow repository edits.

The prospective pipeline supersedes manual sequencing for new forecasts. Historical
evaluation remains blocked where original availability is unknown; do not backdate
observations. See [decision 003](decisions/003-prospective-pipeline.md).

From `apps/api`, after explicit database selection and migration to `b72c904e1a36`:

```powershell
# Collect one bounded page of recent results and upcoming matches, freeze, score.
.venv/Scripts/python.exe -u -m app.pipeline --once --pages 1
# Recurring local worker: delay 300 seconds after each cycle.
.venv/Scripts/python.exe -u -m app.pipeline --interval-seconds 300 --pages 1
# Read-only collector health check; nonzero means failed/stale/not started.
.venv/Scripts/python.exe -m app.pipeline --health
# Freeze/report from existing fresh observations without network collection.
.venv/Scripts/python.exe -m app.pipeline --once --no-collect
```

Keep the worker running on an awake host with Docker/database access and permitted
outbound HTTPS. Stop with Ctrl+C; it finishes the current cycle before exiting.
`--once` returns nonzero after failure. `--experimental` enables individual candidate
models without promotion. Start with the default Elo v1 worker. Standalone
`app.research.generate_models --prospective` supports the same evidence protocol.

`compose.app.yaml` includes a recurring worker sharing the API's artifact volume.
Do not accidentally switch an existing local database to an empty artifact volume:
mount the same ARTIFACT_ROOT or copy and verify all existing artifacts before
switching. The default compose volume is appropriate for a new deployment. On
Docker Desktop the host database URL must use `host.docker.internal`, not localhost.
No real secrets belong in compose files. Worker health checks require a successful
collection-enabled cycle in the last 15 minutes; smoke-only cycles do not qualify.

`GET /api/v1/research/prospective?limit=50&offset=0` returns report metadata, separate
per-model prospective metrics, and paginated frozen forecast history. Pending,
invalidated, and legacy records carry explicit reasons. The dashboard renders this
history and never mixes it with historical diagnostic metrics. The research run
endpoint provides the dataset/feature/model/schedule provenance for each model run.

For AWS, use one EventBridge Scheduler-triggered ECS task running `--once` or one
long-lived worker service. Retain the advisory lock in either case, set job timeout
above observed collection duration, and alert on nonzero exit, FAILED runs, missing
success for 15 minutes, disk space, DB connectivity, and raw-archive failures.
Collection window depth must cover outages and match volume: inspect gaps and run
a reviewed bounded catch-up (`--pages` up to 10) if needed. This is not a promise of
complete coverage during downtime. RDS/S3/ECR/CloudWatch provisioning remains manual.

## Git permission investigation and manual checkpoint

No stale `.git/index.lock` was present. `.git` is owned by the user but contains
explicit deny entries for sandbox identities; no ACL/security settings were changed.
Run the following in your ordinary terminal outside the agent sandbox:

```powershell
Set-Location 'C:\Users\isaac\OneDrive\Desktop\CLUTCHQUANT'
git status --short
git diff --check
git diff
git ls-files --others --exclude-standard
# Review untracked files too, then create a local checkpoint. No push is included.
git add -- .
git diff --cached --stat
git diff --cached
git commit -m "feat: add auditable prospective forecasting pipeline"
```

If the normal terminal is also denied, stop and inspect `Get-Acl .git` with the
machine administrator; do not delete locks or reset ACLs without identifying the
owner/cause. `.env.local`, Python environment files, and artifacts are gitignored;
review the staged diff before committing.

## Local setup

Use Python 3.12, Node 24, Docker, and PostgreSQL 17. From the repository root,
`docker compose up -d` starts the existing local database. From `apps/api`:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt -c requirements.lock
# Set DATABASE_URL to the intended PostgreSQL SQLAlchemy URL before continuing.
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic heads
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic check
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The development fallback points to the existing local clutchquant database.
Outside development, DATABASE_URL is mandatory. `.env.example` is a template;
the Python application does not automatically load it. Inject environment variables
through the shell or deployment service. Never commit credentials.

From `apps/web`, run `npm ci`, then `npm run dev`. Set server-side API_URL in
`.env.local` if needed; the preserved default is `http://127.0.0.1:8000/api/v1`.
`/api/v1/health` checks process health; `/api/v1/ready` checks DB connectivity and head.

## Collection and research

From `apps/api`, use the virtual environment's Python for these modules:

```powershell
.venv/Scripts/python.exe -m app.ingestion.vlr_upcoming
.venv/Scripts/python.exe -m app.ingestion.vlr_recent --pages 2
.venv/Scripts/python.exe -m app.research.audit_matches
.venv/Scripts/python.exe -m app.research.cli snapshot
.venv/Scripts/python.exe -m app.research.cli evaluate --dataset DATASET_SHA256 --validation-start 2025-01-01T00:00:00Z --test-start 2026-01-01T00:00:00Z
.venv/Scripts/python.exe -m app.research.generate_models
```

Schedule upcoming collection before matches and bounded recent-results reconciliation
afterward. Start conservatively and monitor failures/source limits. These network
jobs are now run by the prospective worker. Existing `app.ingestion.vlr` historical
backfill and `vlr_stats_backfill` remain available; inspect their options before a
large run. Fetching history today does not recover historical availability.

Snapshot prints its immutable hash. Evaluate reuses that exact hash and explicit
boundaries; never select tuning boundaries after inspecting holdout results.
Artifacts live under `apps/api/artifacts` by default, excluded from Git. Preserve
all raw/retrieval/dataset/report/run keys together. Missing or altered bytes fail
integrity checks. Use ARTIFACT_ROOT for a durable location shared by jobs and API.

The historical strict generator refuses unknown history. The prospective generator
can use an explicit frozen Elo cold-start prior. `--experimental` permits individual
experimental models when sufficient evidence exists; it never overwrites stored
forecasts. `--ensemble-report HASH` additionally requires supporting evaluation
for the current code/configuration. The old `backtest_elo` and
`generate_elo_forecasts` retain compatibility but use the legacy scheduled-order
protocol; do not treat them as validated observed-time production research.

## Validation

Set TEST_DATABASE_URL to an explicitly selected PostgreSQL test database with
schema-creation permission. Tests isolate their own UUID schemas.

```powershell
# apps/api
.venv/Scripts/python.exe -m pytest -q
# apps/web
npm test
npm run lint
npm run typecheck
npm run build
```

GitHub Actions defines equivalent Linux checks with PostgreSQL. It has not been
executed remotely in this session. Both Dockerfiles run as non-root users.
`docker compose -f compose.app.yaml up --build -d` runs application services with
explicit DATABASE_URL and persistent artifacts. From containers, `localhost` refers
to that container; use the database service hostname or Docker Desktop's
`host.docker.internal` for the existing host-published local database.

## Production migration and deployment

1. Choose an environment, backup/restore policy, budget, and deployment region.
   Provision RDS PostgreSQL privately and verify restore procedures. Separate the
   migration owner from the least-privilege application role.
2. Back up the database and artifacts. Verify sanitized target host/database/role,
   current revision, target head, and reviewed migration SQL. Run one migration
   job using the release image, then `alembic current`, `alembic check`, readiness,
   and controlled read/write smoke checks. Stop on unexpected results. Do not run
   migrations implicitly in every web worker. Duplicate-name migration downgrade
   can fail after legitimate duplicates; do not delete data to force rollback.
3. Push tested images to ECR after authorization. Deploy API and web through ECS/
   Fargate or an appropriate managed container service behind HTTPS. Configure
   API_URL for server-side connectivity and inject secrets through Secrets Manager.
   Keep public human writes disabled until the intended authentication design exists.
4. Provide durable artifact storage shared with jobs. Archive content-addressed
   keys to versioned S3 and test restoration. The current filesystem adapter needs
   a durable shared mount; ephemeral container disks alone are insufficient.
5. Schedule collection and forecast jobs with non-overlapping execution. Send logs
   to CloudWatch and alert on collection gaps, job failures, DB readiness, storage
   failures, and forecast age. Add release/rollback automation and a public URL
   only after end-to-end staging verification.

No AWS resources, remote push, public URL, credentials, or paid services were
created. S3 integration, operational alerts, scheduler wiring, multi-user auth,
load testing, and actual deployment remain work to perform in the target environment.
