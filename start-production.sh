#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${ADMIN_PASSWORD:?Set ADMIN_PASSWORD in hosting environment variables}"
: "${DATA_DIR:?Set DATA_DIR to the persistent disk mount path}"
mkdir -p "$DATA_DIR"
# Sessions and login throttles currently live in this single worker process.
exec python3 -m gunicorn wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 60 --access-logfile - --error-logfile -
