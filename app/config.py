from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_ignore_empty=True, extra='ignore')

    DATABASE_URL: str = 'postgresql+psycopg://test:test@localhost:5432/mydb'
    SQL_ECHO: bool = False
    MEDIA_ROOT_DIR: Path = Path('media/')
    
    @field_validator('MEDIA_ROOT_DIR', mode='before')
    @classmethod
    def convert_to_path(cls, v):
        return Path(v) if isinstance(v, str) else v


settings = Settings()

# Ensure download directory exists
settings.MEDIA_ROOT_DIR.mkdir(parents=True, exist_ok=True)
