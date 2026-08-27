# Media Depot

A web application for crawling, downloading, storing, and managing media content from various social media platforms.


## Running with Docker (recommended)

### First-time setup

Prerequisites: **Docker Desktop** and **uv**. Everything else runs in containers.

```shell
# 1. Config. Nothing here is secret by default; adjust credentials if you like.
cp .env.example .env

# 2. Seed the Douyin service. Pulls its image and writes the state that would
#    otherwise require answering a disclaimer prompt and a menu by hand.
./scripts/setup_douyin.sh

# 3. Extract browser cookies. Must run on the host - see "Cookies" below.
#    Also syncs the Douyin cookie into the Douyin service.
uv run scripts/refresh_cookies.py

# 4. Build and start everything.
docker compose up -d --build
```

Steps 2 and 3 are order-independent. `refresh_cookies.py` creates the Douyin
settings file if it does not exist yet, and `setup_douyin.sh` merges into
whatever is already there, preserving the cookie.

Open <http://localhost:8000>. Check everything came up healthy:

```shell
docker compose ps
```

You should see `api`, `douyin-downloader`, `postgres`, `redis` as `healthy` and
`worker` as `Up`. (`migrate` runs once and exits - that is correct.)

Optional, but recommended:

- **Keep cookies fresh automatically** - install the launchd agent (see
  [Cookies](#cookies)). Without it, cookies go stale and authenticated
  platforms start failing after a day or so.
- **Import an existing library** from another machine (see
  [Importing](#importing-an-existing-library-from-another-machine)).

### Every time after that

```shell
# 1. Docker Desktop must be running. If it is not:
open -a Docker

# 2. Start the stack.
docker compose up -d
```

That is it - no `--build`, no scripts. `docker compose up -d` is idempotent, so
running it when everything is already up does nothing.

**`refresh_cookies.py` does not need to run on every boot.** Cookies live in
`.cache/cookies.txt`, which persists across restarts. They do go stale though,
so either install the launchd agent (see [Cookies](#cookies)) to refresh hourly,
or re-run it by hand when downloads start failing:

```shell
uv run scripts/refresh_cookies.py --check   # how old are they?
uv run scripts/refresh_cookies.py           # refresh now
```

Use `--build` **only after changing application code**, since the source is
copied into the image:

```shell
docker compose up -d --build
```

### Published ports

```
api                 0.0.0.0:8000->8000/tcp     the UI
postgres            127.0.0.1:5433->5432/tcp   manual inspection only
redis               6379/tcp                   not published
douyin-downloader   5555/tcp                   not published
```

`ports:` publishes to the *host*; it has nothing to do with container-to-container
traffic, which goes by service name over the compose network (`postgres:5432`,
`redis:6379`, `douyin-downloader:5555`). Redis and the Douyin service therefore
publish nothing at all - a password-less Redis has no business being reachable
from your network.

**Postgres is published on `127.0.0.1` only.** That prefix is the whole point:
without it Docker binds `0.0.0.0` and a `postgres`/`postgres` database is
reachable by anyone on your wifi. With it, you can point `psql` or a GUI client
(TablePlus, Postico, DBeaver) at it from this machine and nobody else:

```
host      127.0.0.1
port      5433
database  media_depot
user      postgres
password  postgres
```

You can also reach any service without host tooling at all:

```shell
docker compose exec postgres psql -U postgres -d media_depot
docker compose exec redis redis-cli
docker compose exec api uv run scripts/verify_import.py
```

`api` is on all interfaces so you can open the library from a phone or tablet on
the same network. Change it to `127.0.0.1:8000:8000` in `docker-compose.yml` to
restrict it to this machine.

### Everyday commands

```shell
docker compose ps                    # what is running / healthy
docker compose logs -f api worker    # follow logs
docker compose down                  # stop; named volumes keep your data
docker compose restart worker        # restart one service
docker compose up -d --scale worker=4    # more download throughput
```

Submitting downloads: paste a share link into the web UI, or use the CLI:

```shell
uv run cli.py --share 'https://www.bilibili.com/video/BV...'
uv run cli.py --file shares.txt
```

### If something is wrong

| Symptom | Check |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop is not running - `open -a Docker` |
| Downloads fail on XHS / Instagram | Cookies are stale - `uv run scripts/refresh_cookies.py` |
| Douyin fails with `响应内容不是有效的 JSON 数据` | Same command; it syncs the Douyin cookie too |
| A container keeps restarting | `docker compose logs <service>` |
| Schema/DB looks wrong | `docker compose exec api uv run scripts/verify_import.py` |

### The Douyin service

Douyin extraction is handled by DouK-Downloader, pulled from the project's own
published image - no local checkout required:

```
ghcr.io/joeanamier/tiktok-downloader:5.8-dev
```

**Do not switch it to `:latest`.** That tag is still 5.7, which binds its API
server to `127.0.0.1` *inside the container*, making it unreachable both from
the worker and from the published port. 5.8 changed this to `0.0.0.0`. Override
the tag with `DOUYIN_IMAGE` in `.env` if you need to.

`scripts/setup_douyin.sh` reads the menu layout out of whatever image you point
it at and writes the correct `run_command` index into `settings.json`, rather
than hardcoding one - upstream reorders that menu between releases. It also
warns if the image binds to loopback.

**Douyin keeps its own cookie**, separate from `.cache/cookies.txt` - it lives in
the `cookie` field of `services/douyin/Volume/settings.json`. Without it requests
fail with `响应内容不是有效的 JSON 数据` ("response is not valid JSON").

`scripts/refresh_cookies.py` handles this automatically: it pulls the
`douyin.com` cookies out of the browser jar, writes them into that settings file
as a `k=v; k=v` string, and restarts the service so it loads them (that value is
only read at startup). It restarts **only when the cookie actually changed**, so
an hourly refresh will not interrupt in-flight downloads.

```shell
uv run scripts/refresh_cookies.py --check        # is it in sync?
uv run scripts/refresh_cookies.py --skip-douyin  # leave the service alone
uv run scripts/refresh_cookies.py --no-restart   # write it, restart later
```

For public posts the anonymous cookies (`ttwid`, `odin_tt`, `__ac_signature`)
are enough. Logging in to Douyin in your browser adds `sessionid`, which the
script will pick up on the next run; it warns when that is absent.

### Cookies

Authenticated platforms (Xiaohongshu, Instagram, Bilibili) need browser cookies.
Cookie extraction **cannot run inside the container**: browsers encrypt their
cookie database with a key held in the macOS keychain, which a Linux container
cannot reach. Mounting the browser profile does not help.

So extraction happens on the host and the container only reads the result:

```shell
uv run scripts/refresh_cookies.py             # extract from the default browser
uv run scripts/refresh_cookies.py --browser chrome
uv run scripts/refresh_cookies.py --check     # how old is the current file?
```

This writes `.cache/cookies.txt`, which is bind-mounted into the api and worker
containers - a refresh is visible to the running containers immediately, no
restart needed. Containers run with `COOKIES_FROM_BROWSER=none` so they never
attempt extraction; they warn loudly when the file is missing or stale.

To keep it fresh automatically, install the launchd agent (hourly, plus once at
login). launchd is preferred over cron on macOS: cron is sandboxed by the privacy
system and cannot read the browser profile without granting Full Disk Access.

```shell
cp scripts/com.mediadepot.refresh-cookies.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mediadepot.refresh-cookies.plist
launchctl start com.mediadepot.refresh-cookies    # run once now
tail -f .cache/refresh-cookies.log                # watch it work
```

Run the extraction manually once first, so you can grant the keychain prompt
("Always Allow") - a background job cannot answer that dialog.

To stop it: `launchctl unload ~/Library/LaunchAgents/com.mediadepot.refresh-cookies.plist`


## Importing an existing library from another machine

Two separate things have to move: the database and the media files. The database
stores `media_assets.file_path` **relative** to `MEDIA_ROOT_DIR`, so the media
folder's internal structure must be preserved exactly or every file will 404.

### 1. Dump the database on the old machine

```shell
pg_dump -U postgres -Fc media_depot > media_depot.dump
```

`-Fc` is the compressed custom format. Use the **old** machine's `pg_dump`: a dump
from an older PostgreSQL restores into a newer server fine, but not the reverse.

### 2. Copy the media folder

Preserve the subdirectory layout (`bilibili/`, `xhs/`, `ins/`, `douyin/`,
`thumbnail/`, ...). Over the network:

```shell
rsync -avh --progress old-machine:/path/to/media-depot/media/ ./media/
```

Or from an external drive (note the trailing slashes - they matter):

```shell
rsync -avh --progress /Volumes/Drive/media/ ./media/
```

`rsync` is worth it over `cp` here: it resumes after an interruption and skips
files already transferred.

### 3. Restore into the container

```shell
./scripts/import_dump.sh /path/to/media_depot.dump
```

This stops api+worker, recreates the database, restores, creates any tables the
dump lacked, restarts, and runs the verification below. No PostgreSQL client
tools are needed on your Mac - `pg_restore` runs inside the postgres container.

### 4. Verify

```shell
docker compose exec api uv run scripts/verify_import.py
```

Reports row counts, any schema differences between the models and the restored
database, and any media assets whose file is missing on disk.

**The thing most likely to bite:** this project has no Alembic migrations, so the
schema is whatever `create_all()` produced at the time of the dump. If the old
database predates a model change, the restored tables will be missing columns and
`create_all()` will not add them - it only creates missing *tables*. The verify
script lists exactly which ones, and they have to be added by hand:

```sql
ALTER TABLE posts ADD COLUMN some_new_column TEXT;
```


## Todo

- Better post error handling (non-existent/deleted posts)
- Right now, when thumbnail file has the same checksum as a post media asset, we delete/ignore the post media asset (because it is downloaded later than the thumbnail). However, I want to prioritize post media assets over thumbnails.
- Alembic is configured but has no migrations; the schema is created by `scripts/init_db.py`.
