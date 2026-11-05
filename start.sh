#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Ahmed_2024
export DATA_DIR="${DATA_DIR:-/workspace/ahmed-business-data}"
mkdir -p "$DATA_DIR"
if [ -z "${ADMIN_PASSWORD:-}" ]; then
  if [ ! -f "$DATA_DIR/admin-password" ]; then
    (umask 077; python3 -c 'import secrets; print(secrets.token_urlsafe(24))' > "$DATA_DIR/admin-password")
  fi
  ADMIN_PASSWORD="$(cat "$DATA_DIR/admin-password")"
  export ADMIN_PASSWORD
fi
exec python3 server.py
