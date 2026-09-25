from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TelemetryScenario(str, Enum):
    NORMAL = "normal"
    WATCH = "watch"
    MODERATE_SURGE = "moderate-surge"
    CRITICAL_SURGE = "critical-surge"


class TelemetryRecord(BaseModel):
    timestamp: datetime = Field(
        description="Fixed UTC timestamp for this simulated telemetry record."
    )

    station_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identifier of the simulated upstream monitoring station.",
    )

    river_level_m: float = Field(
        ...,
        ge=0,
        le=100,
        description="Simulated river level in metres relative to the demo station datum.",
    )

    river_change_m_per_hour: float = Field(
        ...,
        ge=-20,
        le=20,
        description="Simulated river-level change in metres per hour.",
    )

    upstream_discharge_m3_per_s: float = Field(
        ...,
        ge=0,
        le=100000,
        description=(
            "Simulated upstream discharge in cubic metres per second. "
            "This is demonstration data and is not scientifically calibrated."
        ),
    )

    scenario: TelemetryScenario

    data_source: Literal["SIMULATED_DEMONSTRATION"] = (
        "SIMULATED_DEMONSTRATION"
    )
