from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Values that mean "explicitly turned off" for optional string settings.
# We cannot use an empty string for this: SettingsConfigDict(env_ignore_empty=True)
# makes an empty environment variable fall back to the default instead.
_DISABLED_VALUES = {'none', 'off', 'false', 'disabled', ''}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_ignore_empty=True, extra='ignore')

    DATABASE_URL: str = 'postgresql+psycopg://test:test@localhost:5432/mydb'
    SQL_ECHO: bool = False
    REDIS_URL: str = 'redis://localhost:6379/0'

    # External extraction services. Inside Docker these are compose service names;
    # on the host they are localhost.
    DOUYIN_DOWNLOADER_HOST: str = 'localhost'
    DOUYIN_DOWNLOADER_PORT: int = 5555
    XHS_DOWNLOADER_HOST: str = 'localhost'
    XHS_DOWNLOADER_PORT: int = 5556

    MEDIA_ROOT_DIR: Path = Path('media')
    CACHE_DIR: Path = Path('.cache')

    # Cookies. COOKIES_FROM_BROWSER names the browser yt-dlp should extract from;
    # set it to 'none' to never attempt extraction and only read COOKIES_FILE.
    # Extraction cannot work inside a container - the browser cookie database is
    # encrypted with a key held in the host's keychain - so containers set 'none'
    # and read a file refreshed on the host (see scripts/refresh_cookies.py).
    COOKIES_FROM_BROWSER: Optional[str] = 'edge'
    COOKIES_FILE: Optional[Path] = None  # Defaults to CACHE_DIR / 'cookies.txt'
    COOKIES_REFRESH_INTERVAL: int = 3600  # Default: 1 hour

    JOB_RETRIES: int = 3

    @field_validator('MEDIA_ROOT_DIR', 'CACHE_DIR', 'COOKIES_FILE', mode='before')
    @classmethod
    def convert_to_path(cls, v):
        return Path(v) if isinstance(v, str) else v

    @field_validator('COOKIES_FROM_BROWSER', mode='before')
    @classmethod
    def disabled_to_none(cls, v):
        if isinstance(v, str) and v.strip().lower() in _DISABLED_VALUES:
            return None
        return v

    @property
    def cookies_file(self) -> Path:
        return self.COOKIES_FILE or self.CACHE_DIR / 'cookies.txt'

    @property
    def douyin_api_root(self) -> str:
        return f'http://{self.DOUYIN_DOWNLOADER_HOST}:{self.DOUYIN_DOWNLOADER_PORT}'

    @property
    def xhs_api_root(self) -> str:
        return f'http://{self.XHS_DOWNLOADER_HOST}:{self.XHS_DOWNLOADER_PORT}'


settings = Settings()

# Ensure directories exist
settings.MEDIA_ROOT_DIR.mkdir(parents=True, exist_ok=True)
settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
