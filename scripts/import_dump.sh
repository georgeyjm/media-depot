#!/usr/bin/env bash
# Restore a pg_dump file from another machine into the compose PostgreSQL.
#
# Usage:
#   ./scripts/import_dump.sh /path/to/media_depot.dump
#   ./scripts/import_dump.sh /path/to/media_depot.sql.gz
#
# Accepts custom-format (-Fc, usually .dump), plain SQL (.sql), or gzipped SQL.
#
# This REPLACES the current database. It stops api+worker first so nothing
# writes mid-restore, drops and recreates the database, restores, then brings
# everything back up and runs the schema check.
set -euo pipefail

cd "$(dirname "$0")/.."

DUMP="${1:-}"
if [[ -z "$DUMP" ]]; then
  echo "Usage: $0 <dump-file>" >&2
  exit 1
fi
if [[ ! -f "$DUMP" ]]; then
  echo "No such file: $DUMP" >&2
  exit 1
fi

# Credentials come from .env, the same ones compose feeds the postgres container.
# shellcheck disable=SC1091
set -a; source .env; set +a
DB="${POSTGRES_DB:-media_depot}"
USER="${POSTGRES_USER:-postgres}"

echo "About to REPLACE database '$DB' in the compose postgres container with:"
echo "  $DUMP  ($(du -h "$DUMP" | cut -f1))"
echo
read -r -p "This destroys the current contents of '$DB'. Continue? [y/N] " reply
[[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

echo
echo "==> Stopping api and worker so nothing holds a connection"
docker compose stop api worker >/dev/null

echo "==> Making sure postgres is up"
docker compose up -d postgres >/dev/null
until docker compose exec -T postgres pg_isready -U "$USER" >/dev/null 2>&1; do sleep 1; done

echo "==> Dropping and recreating '$DB'"
docker compose exec -T postgres psql -U "$USER" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB' AND pid <> pg_backend_pid();" >/dev/null
docker compose exec -T postgres psql -U "$USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB\";" >/dev/null
docker compose exec -T postgres psql -U "$USER" -d postgres -c "CREATE DATABASE \"$DB\";" >/dev/null

echo "==> Restoring (this can take a while for a large library)"
case "$DUMP" in
  *.gz)
    gunzip -c "$DUMP" | docker compose exec -T postgres psql -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 >/dev/null
    ;;
  *.sql)
    docker compose exec -T postgres psql -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 < "$DUMP" >/dev/null
    ;;
  *)
    # Custom/directory format. --no-owner/--no-privileges keeps it working even
    # when the old machine used a different postgres role name.
    docker compose exec -T postgres pg_restore -U "$USER" -d "$DB" \
      --no-owner --no-privileges --exit-on-error < "$DUMP"
    ;;
esac

echo "==> Applying any tables the current code expects but the dump lacks"
docker compose run --rm migrate >/dev/null

echo "==> Restarting api and worker"
docker compose up -d api worker >/dev/null

echo
echo "==> Verifying"
docker compose exec -T api uv run scripts/verify_import.py
