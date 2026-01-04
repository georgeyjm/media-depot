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

```
uv run fastapi dev
```

4. Spin up a worker.

```shell
uv run worker.py
```

Note for macOS, set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`.


### Production

For production, we use Docker for easy deployment.

```shell
docker compose up --scale worker=4
```


## Todo

- Better cookie handling (browser cookies cannot be accessed inside Docker)
- Better post error handling (non-existent/deleted posts)
