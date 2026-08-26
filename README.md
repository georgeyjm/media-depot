# Media Depot

A web application for crawling, downloading, storing, and managing media content from various social media platforms.


## Running with Docker (recommended)

One-time setup:

```shell
cp .env.example .env          # adjust credentials if you like
./scripts/setup_douyin.sh     # seeds the Douyin service so it needs no TTY
uv run scripts/refresh_cookies.py   # writes .cache/cookies.txt (see Cookies below)
```

Then, every time:

```shell
docker compose up -d --build
```

That starts postgres, redis, a one-shot database init, the API, a worker, and the
Douyin extraction service. The UI is at http://localhost:8000.

```shell
docker compose logs -f api worker   # follow logs
docker compose ps                   # what is running / healthy
docker compose down                 # stop; named volumes keep your data
docker compose up -d --scale worker=4
```

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


## Running locally (without Docker)

1. Start a PostgreSQL server and a Redis server

```shell
redis-server
```

2. Create the schema

```shell
uv run scripts/init_db.py
```

3. Start the API server

```shell
uv run fastapi run
```

4. Spin up workers

```shell
uv run worker.py
```
Note for macOS, set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`.

5. Run the Douyin extraction service

```shell
docker compose up -d douyin-downloader
```

`.env` describes host-side usage, so `DATABASE_URL`/`REDIS_URL` should point at
`localhost` on the published ports (5433 and 6380 by default). `docker-compose.yml`
overrides them for containers.

You will also need `libmagic` on the host: `brew install libmagic`.


## Todo

- Better post error handling (non-existent/deleted posts)
- Right now, when thumbnail file has the same checksum as a post media asset, we delete/ignore the post media asset (because it is downloaded later than the thumbnail). However, I want to prioritize post media assets over thumbnails.
- Alembic is configured but has no migrations; the schema is created by `scripts/init_db.py`.
