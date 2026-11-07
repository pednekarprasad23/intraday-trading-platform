from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intraday Trading Platform API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    database_url: str = "sqlite+pysqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 3600
    mt5_snapshot_path: str | None = None
    angelone_snapshot_path: str | None = None
    angelone_enabled: bool = False
    historical_data_root: str = "/var/lib/intraday/historical"

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
