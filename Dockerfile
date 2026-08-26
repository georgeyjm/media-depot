FROM python:3.13-slim

# uv: never touch the network at runtime, never re-sync on `uv run`.
# The image is built from the lockfile and stays exactly as built.
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    UV_NO_SYNC=1

# System dependencies:
#   ffmpeg           - yt-dlp merging separate video/audio streams
#   libmagic1        - python-magic, used to sniff downloaded file types
#   (libpq comes from the psycopg[binary] wheel, no system package needed)
#   imagemagick      - `magick`, first choice for HEIC/AVIF -> JPEG in /media
#   libheif-examples - `heif-convert`, the fallback that actually handles HEIC
#                      reliably (`sips` from the same code path is macOS-only)
#   curl             - container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    imagemagick \
    libheif-examples \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependencies first, in their own layer: this only re-runs when the lockfile
# changes, so editing application code rebuilds in seconds.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Application code
COPY . .

# Mount points for the media library and the on-disk cache (cookies, converted
# images). Created here so the paths exist even when nothing is mounted.
RUN mkdir -p media .cache

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
