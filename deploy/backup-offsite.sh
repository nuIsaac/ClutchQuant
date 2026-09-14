#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ]; then echo 'Usage: backup-offsite.sh RCLONE_REMOTE:BUCKET/PREFIX' >&2; exit 2; fi
# Requires an operator-configured rclone remote; no credentials are read by the app.
command -v rclone >/dev/null
mkdir -p deploy/backups
sh deploy/compose.sh stop worker
sh deploy/backup.sh "$(pwd)/deploy/backups"
rclone copy deploy/backups "$1" --checksum
rclone check deploy/backups "$1" --one-way
sh deploy/compose.sh up -d worker
# Failure deliberately leaves worker stopped: repair backup/space issues explicitly.
