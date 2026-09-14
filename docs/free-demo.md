# $0 public proof of concept

The deployment target is Vercel Hobby (Next.js), Render Free Web Service
(FastAPI Docker), Supabase Free (Postgres **and a private Storage bucket**), and
GitHub Actions (short scheduled jobs). Use provider subdomains and HTTPS; no paid
domain, VM, persistent Render worker, disk, or Render database is required.
This is a personal, noncommercial portfolio demo, not production infrastructure.
No resources have been provisioned. The local Compose worker remains supported.

## Deployment order

1. Create free GitHub, Supabase, Render and Vercel accounts as needed. Keep spending
   disabled and do not upgrade plans. Publishing/pushing this repository is a manual
   owner action; review the diff and secret handling first.
2. Create a **separate empty Supabase Free project**. Save its database password.
   Create a **private** Storage bucket named `clutchquant-artifacts`; no public
   upload/read policies. Obtain the project HTTPS URL and server-only legacy
   `service_role` JWT from project API settings. It bypasses Storage RLS: treat it
   as a privileged secret, never a frontend variable or browser token.
3. Use the dashboard's **session pooler** connection on **5432**, suitable for IPv4
   GitHub/Render hosts. Never use transaction pooling on 6543: the cycle holds a
   session advisory lock across transactions. Set `DATABASE_URL` in a private
   shell to `postgresql+psycopg://postgres.PROJECT_REF:ENCODED_PASSWORD@POOLER_HOST:5432/postgres?sslmode=require`.
   Percent-encode username/password special characters; keep the actual dashboard
   host/project reference. Do not print the URL in logs.
4. From `apps/api`, install `requirements.txt` constrained by `requirements.lock`.
   Using the admin connection, inspect `alembic current` and `alembic heads`, run
   `alembic upgrade head`, then `alembic current` and `alembic check`. Expected
   current repository head: `b72c904e1a36`. Stop on unexpected revisions/errors.
   Migrations are an explicit operator step, never API or cron startup behavior.
5. Run `deploy/supabase-demo.sql` as project postgres against this new demo only.
   Assign LOGIN and unique passwords to `cq_demo_api` and `cq_demo_worker` in a
   private administrator session (`ALTER ROLE ... LOGIN PASSWORD ...`). Use their
   pooler usernames `cq_demo_api.PROJECT_REF` and `cq_demo_worker.PROJECT_REF`.
   Verify each connection before continuing. The API has SELECT only; the worker
   has data privileges but no DDL. Existing append-only triggers remain in force.
   RLS and revoked anonymous/authenticated grants protect application tables from
   Supabase's Data API. Reapply/review grants and RLS after future new-table migrations.
6. Configure GitHub secrets below, set repository variable `FREE_DEMO_ENABLED=true`,
   and manually dispatch `Prospective demo cycle` once. Verify success, frozen
   forecast provenance and private bucket objects. A fresh demo intentionally starts
   without imported historical data; Elo's existing explicit cold-start prior applies.
   This does not change or relabel local history. Historical availability is still
   unknown. Do not restore database references without their complete artifact archive.
7. Deploy `render.yaml` as a Free web service (or reproduce its settings in the
   dashboard). Docker context `apps/api`, Dockerfile `apps/api/Dockerfile`, port8000.
   Set the API-role URL and server variables below. Check `/api/v1/health`,
   `/api/v1/ready`, `/api/v1/matches/upcoming` and the frontend's research views.
8. Import the repository in Vercel, select Hobby, root directory `apps/web`, Next.js,
   Node24, install `npm ci`, build `npm run build`. Set server variable
   `API_URL=https://YOUR-SERVICE.onrender.com/api/v1`, then deploy. Use the generated
   `vercel.app` URL. Test loading matches after waking the API and after a cron run.

## Configuration and secrets

Vercel needs **only `API_URL`**, for Production and optional Preview environments.
It is server-side; do not add database or Supabase keys or `NEXT_PUBLIC_*` secrets.
Local `.env.local` remains unchanged. Server-side API requests need no browser CORS.

Render: `DATABASE_URL` (API role/session pooler/SSL), `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`; blueprint supplies `APP_ENV=production`, `PORT=8000`,
`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=0`, `ARTIFACT_BACKEND=supabase`,
`ARTIFACT_ROOT=/tmp/clutchquant-artifacts`, `ARTIFACT_READ_ONLY=true`,
`SUPABASE_ARTIFACT_BUCKET=clutchquant-artifacts`. Leave `HUMAN_FORECAST_TOKEN` unset
so public users cannot submit human forecasts. Readiness checks database connectivity
and migration head, not collection freshness or the Storage service.

GitHub repository secrets: **`DEMO_DATABASE_URL`** (worker role/session pooler/SSL),
**`SUPABASE_URL`**, **`SUPABASE_SERVICE_ROLE_KEY`**. No Vercel/Render API credential
is needed. Repository variable **`FREE_DEMO_ENABLED=true`** is the explicit enable
switch; unset/false disables all collection jobs. No secrets are exposed to PR jobs.
`deploy/.env.demo.example` documents server configuration; real `.env.demo` is ignored
and is not automatically loaded by Python. Export variables through the shell/provider.

## Scheduled and persistent operation

`.github/workflows/prospective-demo.yml` runs **`17 */3 * * *` UTC**: 00:17,
03:17,06:17,09:17,12:17,15:17,18:17,21:17 daily. It also supports manual dispatch.
The command is `python -u -m app.pipeline --once --demo-cycle --pages 1`.
Upcoming sync captures timestamped observations; eligible forecasts freeze before
completed-results sync; scoring reads saved forecasts and verifies their artifacts.
No experimental models are enabled. Failures exit nonzero, overlap skips exit zero.

Actions concurrency serializes scheduled/manual jobs; a PostgreSQL session advisory
lock also protects against another worker. Database uniqueness makes identical
retrieval evidence and match/model forecasts idempotent. A later real fetch is a new
observation with its actual new timestamp, not a duplicate retry. Partially completed
runs may leave valid immutable evidence/forecasts; retries never rewrite them. A kill
or timeout releases the connection lock, but can leave only a STARTED artifact;
inspect Actions status as well as pipeline_runs. No successful result is fabricated.

The existing `python -m app.pipeline` persistent loop and `compose.app.yaml` retain
their original results-first order and five-minute interval. Do not point a second
local collector at the demo unless deliberately coordinating collection. The local
worker's 15-minute health freshness threshold remains unchanged and is **not** an
appropriate health check for the three-hour demo schedule.

Artifacts upload to Supabase **before** database references are persisted. Objects
are gzip-compressed at `v1/KIND/ORIGINAL_SHA256.gz`, without upsert; readers validate
the uncompressed original hash. Ephemeral local caches are disposable. Quota,
missing-object or integrity errors fail closed; never prune evidence silently.

## Free-tier limits, monitoring and recovery

- [Render Free](https://render.com/docs/free) sleeps after 15 idle minutes and has
  ephemeral disk. Cold starts can exceed the frontend request timeout; users may
  need to retry. Do not use keepalive traffic. Collection talks directly to Supabase
  and continues while Render sleeps. Watch Render logs and readiness failures.
- [Supabase Free](https://supabase.com/pricing) includes 500MB database and 1GB file
  storage with limited egress; it may pause inactive projects. Raw evidence and
  growing dataset snapshots will eventually exhaust quotas. Monitor usage weekly;
  disable the workflow before limits and export the complete DB + private bucket.
  Free hosting is not an indefinite archival/backup guarantee. Never delete referenced
  objects to make a run succeed. Downloading a database alone is not a full backup.
- [GitHub Actions](https://docs.github.com/en/billing/reference/product-usage-included)
  Free private repositories include 2,000 runner minutes/month shared with CI.
  Eight jobs/day capped at six minutes use at most 1,488 minutes in a 31-day month
  before manual runs/retries/CI. This is a budget bound, not measured job duration.
  Public standard runners are free. Keep spending at zero; exhausted quotas stop work.
- [Schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
  run on the default branch, can be delayed/dropped, and public inactive repositories
  can have schedules disabled after60 days. Enable failure notifications and inspect
  the latest Actions run and pipeline_runs daily. Three-hour spacing and one listing
  page can miss matches/results; unchanged 900-second evidence freshness still applies
  at freeze time. Coverage gaps are expected and must remain explicit.
- [Vercel Hobby](https://vercel.com/docs/plans/hobby) is for personal noncommercial
  use and has resource limits; commercial use needs reassessment. Use an eligible
  personal repository/account. Provider-generated HTTPS URLs cost no domain fee.

Before upgrades: disable collection, export the application database and all bucket
objects to private offline storage, record commit and migration revision, then apply
reviewed migrations with the admin URL. Redeploy API/frontend and dispatch a smoke
cycle before re-enabling the schedule. For code rollback select the prior provider
deployment/commit; do not blindly downgrade schema or overwrite append-only records.
Restore to a separate empty project and verify hashes/row counts/head before switching
URLs. Preserve observation timestamps during recovery; missing collection intervals
remain missing. Supabase-managed auth/storage schemas must not be overwritten by a
local cluster dump. Existing local history remains intact and separate from this demo.

The optional self-hosted files in `compose.production.yaml` and `deploy/` are retained
for recovery drills; [the VM guide](deployment.md) is an archived alternative, not
the demo default. No live cloud smoke test can be claimed before account setup.
