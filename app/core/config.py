from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    census_api_key: str
    bls_api_key: str
    anthropic_api_key: str
    fetcher_timeout_seconds: int = 8
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton; usable as a FastAPI dependency."""
    return Settings()
