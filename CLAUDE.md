# Media Depot - Project Guide for Claude

A web application for crawling, downloading, storing, and managing media content from various social media platforms (Xiaohongshu/XHS, Instagram, Bilibili, Douyin).

## Architecture Overview

### Tech Stack
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Task Queue**: Redis + RQ workers
- **Package Manager**: uv
- **Downloads**: yt-dlp, gallery-dl

### Project Structure
```
app/
├── handlers/          # Platform-specific handlers
│   ├── BaseHandler.py    # Abstract base class
│   ├── XhsHandler.py     # Xiaohongshu (小红书)
│   ├── InsHandler.py     # Instagram
│   ├── BilibiliHandler.py
│   └── DouyinHandler.py
├── models/            # SQLAlchemy database models
│   ├── platform.py
│   ├── post.py
│   ├── media_asset.py
│   ├── post_media.py    # Join table: Post ↔ MediaAsset
│   ├── creator.py
│   ├── job.py
│   └── enums.py
├── schemas/           # Pydantic schemas
├── utils/
│   ├── download.py    # Core download logic
│   ├── db.py          # Database helpers
│   └── cookies.py     # Cookie management
├── main.py           # FastAPI app entry point
└── workers.py        # RQ worker task definitions
worker.py             # Worker process entry point
```

## Core Concepts

### 1. Handler Pattern

All platform handlers inherit from `BaseHandler` and implement:
- **`extract_info()`**: Scrapes post metadata without downloading
- **`download()`**: Downloads all media assets for a post

**Key Class Variables:**
```python
PLATFORM_NAME: str           # e.g., 'xhs', 'ins'
PLATFORM_DISPLAY_NAME: str   # e.g., 'Xiaohongshu', 'Instagram'
FULL_URL_PATTERNS: tuple     # Regex patterns for full URLs
SHORT_URL_PATTERNS: tuple    # Regex patterns for short/share URLs
USE_COOKIES: bool            # Whether platform requires auth cookies
PLATFORM: Platform           # Set during initialization
DOWNLOAD_DIR: Path           # Media download directory
```

**Handler Lifecycle:**
1. `supports_share(share_text)` - Check if handler can process URL
2. `extract_url_from_share(share_text)` - Extract clean URL
3. `resolve()` - Follow redirects to canonical URL
4. `extract_info()` - Scrape post metadata → returns `PostInfo`
5. `download(db, post)` - Download media → returns `list[PostMedia]`

### 2. Data Model

**Key relationships:**
```
Platform (1) ──→ (N) Post
Post (1) ──→ (N) PostMedia (N) ──→ (1) MediaAsset
Post (1) ──→ (1) MediaAsset (thumbnail)
Creator (1) ──→ (N) Post
Creator (1) ──→ (1) MediaAsset (profile_pic)
Post (1) ──→ (1) Job
```

**Important:** `MediaAsset` is deduplicated by `checksum_sha256` - same file is never stored twice.

### 3. Download Flow

**Two main download paths:**

**A. yt-dlp (for Bilibili, Douyin videos):**
```python
download_yt_dlp(url, download_dir, filename, cookies_file)
```

**B. gallery-dl (for Instagram posts):**
```python
download_gallery_dl(url, download_dir, filename, extractor, extra_options)
```

**C. Direct HTTP download (for XHS images, thumbnails):**
```python
download_file(url, download_dir, filename, use_cookies, chunk_size)
```

**Key features:**
- **Resume support**: Downloads can resume from partial files using HTTP Range requests
- **Cookie handling**: Netscape-format cookie file at `~/.crawler/cookies.txt`
- **Deduplication**: Files are deduplicated by SHA256 checksum

## Platform-Specific Notes

### Xiaohongshu (XHS)

**URL formats:**
- Stable: `https://ci.xiaohongshu.com/{fileId}` (preferred)
- Time-limited CDN: `http://sns-webpic-qc.xhscdn.com/.../...!suffix` (expires quickly)

**Critical issue:**
- XHS CDN URLs with timestamps expire within minutes
- Always prefer `fileId` over `urlDefault` when extracting thumbnails
- If only `urlDefault` is available, consider skipping thumbnail (see `app/handlers/XhsHandler.py` line 238-242)

**Media handling:**
- Images: Direct download from `ci.xiaohongshu.com`
- Videos: Two extraction methods:
  1. `extract_media_urls()` - Origin quality (preferred)
  2. `extract_media_urls_non_origin()` - Fallback for non-origin streams
  - Sets `metadata['using_non_origin_video'] = True` when using fallback
- Live photos: Downloads both image and video components

### Instagram

**Implementation:** Uses `gallery-dl` Python API (not CLI)

**Key techniques:**
- `DataJob(url, file=None)` - Extract metadata without downloading (set `file=None` to suppress JSON output)
- `DownloadJob(url)` - Download media
- Track downloaded files by replacing `job.out` with custom `_GalleryDlPathCollector`

**Cookie requirement:** Instagram requires authentication cookies in `~/.crawler/cookies.txt`

## Common Patterns

### Creating/Fetching Posts

```python
from app.utils.db import get_or_create_post

post = get_or_create_post(
    db=db,
    platform=platform,
    post_info=post_info,
    download_thumbnail=True,  # Auto-download thumbnail
    commit=True
)
```

### Downloading Media Assets

```python
from app.utils.db import download_media_asset_from_url

media_asset = download_media_asset_from_url(
    db=db,
    url=media_url,
    media_type=MediaType.image,
    download_dir=handler.DOWNLOAD_DIR,
    filename='my_file',
    use_cookies=True  # For platforms requiring auth
)
```

### Linking Media to Posts

```python
from app.utils.db import link_post_media_asset

post_media = link_post_media_asset(
    db=db,
    post=post,
    media_asset=media_asset,
    position=0  # Order in carousel
)
```

## Development Workflow

### Running locally

1. Start PostgreSQL
2. Start Redis: `redis-server`
3. Start API: `uv run fastapi run`
4. Start workers: `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run worker.py` (macOS)
5. External services: `docker start -i douyin-downloader`

### Database migrations

Using Alembic (assumed):
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Adding a new platform handler

1. Create `app/handlers/NewPlatformHandler.py` extending `BaseHandler`
2. Implement required methods and class variables
3. Add to `app/handlers/__init__.py` HANDLERS list
4. Test with sample URLs

## Known Issues & Gotchas

### 1. Thumbnail vs Post Media Checksum Conflicts

**Issue:** When thumbnail has same checksum as post media asset, the post media gets deleted/ignored because it's downloaded later.

**Desired behavior:** Prioritize post media assets over thumbnails.

**Current workaround:** None implemented yet.

### 2. XHS Time-Limited URLs

**Issue:** `urlDefault` URLs from XHS API expire within minutes, causing 404s during download.

**Solution:** Prefer `fileId`-based URLs which are stable. Skip thumbnails if only `urlDefault` is available.

### 3. gallery-dl Output Suppression

**Issue:** `DataJob` prints verbose JSON output to stdout by default.

**Solution:** Pass `file=None` to constructor: `DataJob(url, file=None)`

### 4. URL Length Limits

**Issue:** Instagram/social media CDN URLs with signatures can exceed VARCHAR(1000).

**Solution:** Use `Text` type for `MediaAsset.url` column (already fixed).

### 5. Download Resume Edge Cases

**Issue:** If server doesn't send `Accept-Ranges: bytes`, resume is disabled and variables may not be set.

**Debug approach:** Add logging before line 504-512 in `app/utils/download.py` to trace request flow.

### 6. XHS CDN Accept-Encoding Rejection

**Issue:** XHS CDN returns 404 errors when certain Accept-Encoding values are sent, even though HEAD requests succeed with 200.

**Root cause:** XHS CDN is very strict about compression encodings:
- Rejects `identity` (no compression) completely
- Intermittently rejects newer encodings like `br` (Brotli) or `zstd` (Zstandard)
- Only reliably supports the universal standards: `gzip` and `deflate`

**Solution:** Use `Accept-Encoding: gzip, deflate` in request headers (already fixed in `app/utils/download.py` line 473).

**Why this works:**
- `gzip` and `deflate` are the original HTTP compression standards (1990s/2000s)
- Supported by virtually every web server and CDN globally
- httpx automatically decompresses these formats
- Browsers also primarily receive `gzip` responses despite advertising `br` support

**Symptoms:**
- HEAD request returns 200 OK
- GET request returns 404 Not Found
- Works sometimes with `br/zstd`, fails other times (non-deterministic)
- Changing to `gzip, deflate` makes it consistently reliable
- Manual browser testing works (browsers also fall back to gzip in practice)

## Debugging Tips

### Enable verbose download logging

Add debug prints in `app/utils/download.py`:
```python
print(f'[DEBUG] URL: {repr(url)}')
print(f'[DEBUG] HEAD response: {test_response.status_code}')
print(f'[DEBUG] Headers: {dict(test_response.headers)}')
```

### Check what handler handles a URL

```python
from app.handlers import HANDLERS
url = "https://www.xiaohongshu.com/explore/..."
for handler_cls in HANDLERS:
    if handler_cls.supports_share(url):
        print(f"Handled by: {handler_cls.PLATFORM_NAME}")
```

### Inspect database state

```python
from app.database import get_session
from app.models import Post, MediaAsset

with get_session() as db:
    post = db.query(Post).filter_by(platform_post_id='xxx').first()
    print(post.media_items)  # List of PostMedia
    print(post.thumbnail)    # MediaAsset or None
```

## Code Style Preferences

- **Type hints**: Use extensively (already in use)
- **Error handling**: Prefer explicit exception handling over silent failures
- **Comments**: Only add where logic isn't self-evident
- **Abstractions**: Avoid premature abstraction - prefer simple, direct code
- **Backwards compatibility**: No need for compatibility hacks - delete unused code completely

## Important Files to Know

- `app/utils/download.py` - All download logic, resume support, file handling
- `app/utils/db.py` - Database helper functions for creating/linking entities
- `app/handlers/BaseHandler.py` - Handler interface and shared functionality
- `app/models/` - SQLAlchemy models defining database schema
- `~/.crawler/cookies.txt` - Netscape-format cookies for authenticated platforms

## External Dependencies

- **yt-dlp**: Video downloads (Bilibili, Douyin)
- **gallery-dl**: Instagram downloads
- **httpx**: HTTP client with resume support
- **BeautifulSoup**: HTML parsing
- **SQLAlchemy**: ORM
- **RQ**: Task queue
- **FastAPI**: Web framework

## Testing URLs

Keep sample URLs for each platform for testing:
- XHS: `https://www.xiaohongshu.com/explore/...`
- Instagram: `https://www.instagram.com/p/...` or `https://www.instagram.com/reel/...`
- Bilibili: `https://www.bilibili.com/video/...`
- Douyin: `https://www.douyin.com/video/...`
