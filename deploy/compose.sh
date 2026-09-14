#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for key in POSTGRES_PASSWORD APP_DB_PASSWORD; do
  if ! grep -Eq "^${key}=[0-9a-f]{64}$" deploy/.env.production; then
    echo "Set $key to an independently generated 64-character hex secret" >&2; exit 2
  fi
done
if ! grep -Eq '^RELEASE_TAG=[0-9a-f]{7,40}$' deploy/.env.production; then
  echo 'Set RELEASE_TAG to the reviewed release commit' >&2; exit 2
fi
# The reviewed env file is authoritative, not a stale interactive shell export.
unset POSTGRES_PASSWORD APP_DB_PASSWORD RELEASE_TAG COMPOSE_PROJECT_NAME CADDY_SITE ACME_EMAIL DATA_DIR WORKER_INTERVAL_SECONDS WORKER_PAGES
exec docker compose --env-file deploy/.env.production -f compose.production.yaml "$@"
