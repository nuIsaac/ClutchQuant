# 12:12 identity and deployment compatibility

Display name: **12:12**, pronounced **twelve to twelve**. Infrastructure slug:
`twelve-twelve`; code identifier: `twelve_twelve`. The product preserves the
existing forecasting models, API routes, immutable records and deployment targets.

## Retained identifiers (not display branding)

| Location | Retained identity | Why / removal gate |
|---|---|---|
| `apps/api/app/legacy.py` | Original local DB connection and artifact bucket | Existing data must remain readable. Override via existing environment interfaces only after verified migration. |
| `compose.yaml`, `compose.production.yaml` | Existing database/users; production roles | Postgres initialization variables do not rename existing databases. No SQL rename is necessary for this release. |
| `deploy/.env.example` | Existing production project and DATA_DIR | Changing these can create another stack or empty storage. New sites can choose new names; upgrades retain exact values. |
| `render.yaml` | Existing Render resource name and artifact bucket | A blueprint rename can create another service. Rename the provider display name separately after approval; do not repoint storage. |
| Scheduled workflow and demo env example | Existing artifact bucket | Readers and writers must use the same immutable archive. Cache directory names have changed safely. |
| Applied Alembic migrations, `deploy/init-db.sh`, `deploy/supabase-demo.sql`, PostgreSQL contract tests | `cq_*` roles, RLS policies and append-only functions/triggers | Applied history and permissions remain unchanged. A future physical rename needs a new migration, fresh-install/upgrade tests and restore rehearsal. |
| `apps/web/src/lib/watchlist.ts`, its tests | `cq-watchlist` | Same-origin fallback migration to `twelve-twelve:watchlist:v1`; dual-write permits rollback. No legacy key appears in visible copy. |
| `apps/web/src/lib/legacy.ts`, README/demo links | Original repository and public hostname | Real working URLs remain until approved provider rename/domain cutover. Do not publish nonexistent URLs. |
| `docs/legacy/` | Historical names, paths, observations and URLs | Immutable historical verification evidence; not current deployment instructions. |
| Active deployment instructions and smoke drill | Existing DB targets and roles | Commands must operate on the real compatibility deployment. |

## Rollout sequence

1. Review the branch and validation report. Keep all existing API_URL, database,
   Supabase, credentials and artifact settings. No credential rotation is needed.
2. Back up database and artifacts together with writers quiesced; restore to an
   isolated target and verify hashes and history counts before any storage move.
3. Build `twelve-twelve-api:RELEASE_TAG` and `twelve-twelve-web:RELEASE_TAG` from the
   reviewed commit. The API/migration/worker share the same image. Preserve the
   existing production Compose project and DATA_DIR. Retain old images for rollback.
4. Local Compose: inspect the actual old container mount and set POSTGRES_VOLUME
   to that volume. The volume is **external and required**, so Compose cannot
   silently create an empty replacement. Stop the old database container before
   starting the newly named one on port 5432. Never run two databases on one volume.
   For a genuinely new local database, explicitly create a new named volume and
   supply its name; this is a separate bootstrap decision, not an upgrade.
5. Install the backup template as `twelve-twelve-backup.service` with the actual
   checkout directory and **existing** remote backup prefix. Copying the example's
   new path/prefix is appropriate only for a new installation. Disable the old
   timer before enabling `twelve-twelve-backup.timer`; verify a backup and restore.
6. Publish application changes to the existing hosting resources first. Verify
   readiness, routes, artifacts, scheduled collection, health monitoring and saved
   watchlists. The health `service` value is now `twelve-twelve-api`; update monitors
   which assert the old string. Status, version and route shapes are unchanged.
7. After explicit approval, rename GitHub to an available `twelve-twelve` slug,
   update description to “12:12 — Competitive Valorant analytics, forecasting, and
   calibration.” Upload `apps/web/src/app/opengraph-image.png` as social preview.
   Update the repository URL in `src/lib/legacy.ts`, origin remote and connected
   hosting settings after verifying the new URL. Do not assume provider hooks move.
8. A public hostname cutover needs a separate plan: localStorage is origin-bound.
   The same-origin migration cannot move watchlists to another hostname. Retain
   the current origin until an export/import or user migration path is agreed.
   Configure SITE_URL at build time to the final public origin for social metadata.

Rollback uses the previous application images and original infrastructure targets;
watchlist dual-write keeps the original app usable. No schema or historical-artifact
migration is required by this release. This file intentionally documents legacy
names; the application must not display them as branding.
