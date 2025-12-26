from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_ignore_empty=True, extra='ignore')

    DATABASE_URL: str = 'postgresql+psycopg://test:test@localhost:5432/mydb'
    SQL_ECHO: bool = False


settings = Settings()
