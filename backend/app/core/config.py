from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FlashFlood API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    weather_upstream_latitude: float = Field(default=26.31393, ge=-90, le=90)
    weather_upstream_longitude: float = Field(default=94.51675, ge=-180, le=180)

    weather_downstream_latitude: float = Field(default=27.0280, ge=-90, le=90)
    weather_downstream_longitude: float = Field(default=95.0312, ge=-180, le=180)

    weather_forecast_horizon_hours: int = Field(default=6, gt=0)
    weather_timeout_seconds: float = Field(default=5.0, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()