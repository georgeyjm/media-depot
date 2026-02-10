# Media Depot

A web application for crawling, downloading, storing, and managing media content from various social media platforms.


## Running

### Development

1. Start a PostgreSQL server

2. Start a Redis server

```shell
redis-server
```

3. Start the API server

```shell
uv run fastapi run
```

4. Spin up workers.

```shell
uv run worker.py
```
Note for macOS, set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`.

5. Run external media extraction servers

```shell
docker start -i douyin-downloader
uv run main.py api
```


### Production

For production, we use Docker for easy deployment.

```shell
docker compose up --scale worker=4
```


## Todo

- Better cookie handling (browser cookies cannot be accessed inside Docker)
- Better post error handling (non-existent/deleted posts)
- Right now, when thumbnail file has the same checksum as a post media asset, we delete/ignore the post media asset (because it is downloaded later than the thumbnail). However, I want to prioritize post media assets over thumbnails.
