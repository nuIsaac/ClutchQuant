#!/bin/sh
# Quiesce ALL writers before invoking. No automatic pruning or destructive cleanup.
set -eu
umask 077
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
  echo 'Usage: sh deploy/backup.sh EXISTING_ABSOLUTE_BACKUP_DIRECTORY' >&2; exit 2
fi
case "$1" in /*) ;; *) echo 'Use an absolute backup directory' >&2; exit 2;; esac
if [ -n "$(sh deploy/compose.sh ps --status running --quiet worker)" ]; then
  echo 'Stop the worker and other writers before a paired backup' >&2; exit 1
fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="$1/$stamp"
mkdir "$destination"
sh deploy/compose.sh exec -T db pg_dump -U cq_owner -d clutchquant -Fc --no-owner --no-acl > "$destination/database.dump"
sh deploy/compose.sh run --rm --no-deps --entrypoint tar worker -C /data/artifacts -cf - . > "$destination/artifacts.tar"
sh deploy/compose.sh images > "$destination/images.txt"
sh deploy/compose.sh run --rm --no-deps migrate python -m alembic current > "$destination/revision.txt"
(cd "$destination" && sha256sum database.dump artifacts.tar > SHA256SUMS)
echo "Backup complete: $destination. Copy off-host and verify before resuming writes."
