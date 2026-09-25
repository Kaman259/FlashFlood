from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


class RiskAssessmentRequest(BaseModel):
    live_rainfall_intensity_mm_per_hour: float = Field(
        ...,
        ge=0,
        le=500,
        description="Current/live rainfall intensity in millimetres per hour.",
    )

    forecast_rainfall_intensity_mm_per_hour: float = Field(
        ...,
        ge=0,
        le=500,
        description="Forecast rainfall intensity in millimetres per hour.",
    )

    river_level_m: float = Field(
        ...,
        ge=0,
        le=100,
        description="Current river level in metres relative to the demo station datum.",
    )

    river_change_m_per_hour: float = Field(
        ...,
        ge=-20,
        le=20,
        description="River-level change in metres per hour. Negative values indicate falling level.",
    )

    upstream_discharge_m3_per_s: float = Field(
        ...,
        ge=0,
        le=100000,
        description=(
            "Upstream discharge in cubic metres per second. "
            "Prototype discharge thresholds are demo-station values only."
        ),
    )

    station_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Optional monitoring station identifier.",
    )


class RiskAssessmentResponse(BaseModel):
    risk_level: RiskLevel
    risk_score: int = Field(ge=0, le=100)
    reasons: list[str]
    recommended_action: str
    warning_message: str
