from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class WeatherLocationRole(str, Enum):
    UPSTREAM = "UPSTREAM"
    DOWNSTREAM = "DOWNSTREAM"


class WeatherDataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class WeatherCoverageStatus(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class WeatherFailureCode(str, Enum):
    TIMEOUT = "TIMEOUT"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    HTTP_ERROR = "HTTP_ERROR"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_UNIT = "INVALID_UNIT"
    INSUFFICIENT_FORECAST_DATA = "INSUFFICIENT_FORECAST_DATA"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"


class LocationWeatherData(BaseModel):
    location_role: WeatherLocationRole
    location_name: str = Field(min_length=1)

    requested_latitude: float
    requested_longitude: float

    provider_latitude: float | None = Field(default=None, ge=-90, le=90)
    provider_longitude: float | None = Field(default=None, ge=-180, le=180)

    source: Literal["OPEN_METEO"] = "OPEN_METEO"
    status: WeatherDataStatus

    observed_at: datetime | None = None

    live_rainfall_intensity_mm_per_hour: float | None = Field(default=None, ge=0)
    forecast_rainfall_intensity_mm_per_hour: float | None = Field(default=None, ge=0)

    forecast_horizon_hours: int | None = Field(default=None, gt=0)
    forecast_window_start: datetime | None = None
    forecast_window_end: datetime | None = None
    forecast_peak_time: datetime | None = None

    rainfall_unit: Literal["mm/hour"] | None = None
    current_interval_seconds: float | None = Field(default=None, gt=0)

    failure_code: WeatherFailureCode | None = None
    failure_message: str | None = None


class WeatherSnapshot(BaseModel):
    upstream: LocationWeatherData
    downstream: LocationWeatherData
    coverage_status: WeatherCoverageStatus

    aggregated_live_rainfall_intensity_mm_per_hour: float | None = Field(
        default=None,
        ge=0,
    )
    aggregated_forecast_rainfall_intensity_mm_per_hour: float | None = Field(
        default=None,
        ge=0,
    )

    live_driver_locations: list[WeatherLocationRole] = Field(default_factory=list)
    forecast_driver_locations: list[WeatherLocationRole] = Field(default_factory=list)

    risk_input_ready: bool = False