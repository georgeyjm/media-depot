#!/usr/bin/env bash
# Prepare the DouK-Downloader (douyin-downloader) state directory so the service
# starts straight into Web API mode with no interactive prompts.
#
# It normally needs a TTY for two reasons:
#   1. a one-time disclaimer prompt, stored as Disclaimer=1 in its SQLite db
#   2. a menu asking which mode to run; settings.json "run_command" pre-answers it
#
# Both live in /app/Volume, so we seed that directory on the host and mount it.
#
# The menu index is NOT hardcoded: upstream reorders that menu between releases,
# so we read it out of the actual image and find "Web API" by the method it is
# bound to (self.server). We also check the image binds its server to 0.0.0.0 -
# older published tags use 127.0.0.1, which is unreachable across containers.
#
# Run once: ./scripts/setup_douyin.sh
set -euo pipefail

cd "$(dirname "$0")/.."
VOLUME_DIR="services/douyin/Volume"
mkdir -p "$VOLUME_DIR"

# Same default as docker-compose.yml
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi
IMAGE="${DOUYIN_IMAGE:-ghcr.io/joeanamier/tiktok-downloader:5.8-dev}"

echo "Image: $IMAGE"
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
  echo "  pulling ..."
  docker pull "$IMAGE"
}

# If a hand-built container is still around, copy its state first - that is
# where a previously configured Douyin cookie lives.
if docker inspect douyin-downloader >/dev/null 2>&1; then
  echo "Found existing 'douyin-downloader' container; copying its /app/Volume ..."
  docker cp douyin-downloader:/app/Volume/. "$VOLUME_DIR/" 2>/dev/null \
    || echo "  (nothing to copy - continuing)"
fi

echo "Inspecting image ..."
SOURCES="$(mktemp)"
trap 'rm -f "$SOURCES"' EXIT
docker run --rm --entrypoint sh "$IMAGE" -c \
  'echo "===MENU==="; cat /app/src/application/TikTokDownloader.py; echo "===STATIC==="; cat /app/src/custom/static.py' \
  > "$SOURCES"

python3 - "$VOLUME_DIR" "$SOURCES" <<'PY'
import json
import re
import sqlite3
import sys
from pathlib import Path

volume = Path(sys.argv[1])
blob = Path(sys.argv[2]).read_text()

menu_src, static_src = blob.split('===STATIC===', 1)
menu_src = menu_src.split('===MENU===', 1)[1]

# --- 1. Which menu index is Web API mode? -----------------------------------
# The menu is a tuple of (label, self.<method>) pairs. Commented-out entries are
# not part of the tuple, so they must not be counted.
block = re.search(r'__function_menu\s*=\s*\((.*?)\n\s*\)\n', menu_src, re.S)
if not block:
    sys.exit('Could not locate __function_menu in the image - upstream layout changed.')

entries = []
for line in block.group(1).splitlines():
    stripped = line.strip()
    if stripped.startswith('#'):
        continue
    m = re.search(r'self\.(\w+)\s*,?\s*\)\s*,\s*$', stripped)
    if m:
        entries.append(m.group(1))

if 'server' not in entries:
    sys.exit(f'No "server" entry in the menu; found: {entries}')
index = entries.index('server') + 1  # the app does int(mode) - 1
print(f'  Web API mode is menu option {index} (of {len(entries)} active entries)')

# --- 2. Does the server bind somewhere reachable? ---------------------------
host = re.search(r'^SERVER_HOST\s*=\s*["\']([^"\']+)', static_src, re.M)
host = host.group(1) if host else '?'
if host in ('127.0.0.1', 'localhost'):
    print()
    print(f'  WARNING: this image binds its API to {host} INSIDE the container.')
    print('  Other containers and the published port cannot reach it. Use a 5.8+')
    print('  tag (e.g. ghcr.io/joeanamier/tiktok-downloader:5.8-dev).')
    print()
else:
    print(f'  Server binds to {host} - reachable from other containers.')

# --- 3. settings.json: pre-select the mode ---------------------------------
settings_path = volume / 'settings.json'
settings = {}
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        print(f'  {settings_path} is not valid JSON; replacing it')
settings['run_command'] = str(index)
settings_path.write_text(json.dumps(settings, indent=4, ensure_ascii=False), encoding='utf-8')
print(f'  {settings_path}: run_command={index}')

# --- 4. SQLite db: accept the disclaimer up front --------------------------
# The app seeds its defaults with INSERT OR IGNORE, so a row written here wins.
db_path = volume / 'DouK-Downloader.db'
conn = sqlite3.connect(db_path)
try:
    conn.execute(
        'CREATE TABLE IF NOT EXISTS config_data ('
        'NAME TEXT PRIMARY KEY, VALUE INTEGER NOT NULL CHECK(VALUE IN (0, 1)));'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS option_data (NAME TEXT PRIMARY KEY, VALUE TEXT NOT NULL);'
    )
    conn.execute("REPLACE INTO config_data (NAME, VALUE) VALUES ('Disclaimer', 1);")
    conn.execute("INSERT OR IGNORE INTO config_data (NAME, VALUE) VALUES ('Record', 1), ('Logger', 0);")
    conn.execute("INSERT OR IGNORE INTO option_data (NAME, VALUE) VALUES ('Language', 'zh_CN');")
    conn.commit()
finally:
    conn.close()
print(f'  {db_path}: disclaimer accepted')
PY

echo
echo "Done. 'docker compose up -d' will now start douyin-downloader unattended."
echo "If Douyin downloads fail with an auth error, its cookie is missing. Either"
echo "paste one into the \"cookie\" field of $VOLUME_DIR/settings.json, or set"
echo "\"run_command\" to \"\" there and run the menu once:"
echo "  docker compose run --rm douyin-downloader"
echo "(remember to restore run_command afterwards, or re-run this script)"
