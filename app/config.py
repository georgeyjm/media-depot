from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_ignore_empty=True, extra='ignore')

    DATABASE_URL: str = 'postgresql+psycopg://test:test@localhost:5432/mydb'
    SQL_ECHO: bool = False
    REDIS_URL: str = 'redis://localhost:6379/0'
    MEDIA_ROOT_DIR: Path = Path('media')
    CACHE_DIR: Path = Path('.cache')
    COOKIES_REFRESH_INTERVAL: int = 3600  # Default: 1 hour
    JOB_RETRIES: int = 3
    
    @field_validator('MEDIA_ROOT_DIR', 'CACHE_DIR', mode='before')
    @classmethod
    def convert_to_path(cls, v):
        return Path(v) if isinstance(v, str) else v


settings = Settings()

# Ensure directories exist
settings.MEDIA_ROOT_DIR.mkdir(parents=True, exist_ok=True)
settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
