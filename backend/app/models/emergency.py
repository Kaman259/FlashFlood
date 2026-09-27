from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmergencyCategory(str, Enum):
    FLOODING = "FLOODING"
    TRAPPED = "TRAPPED"
    MEDICAL = "MEDICAL"
    EVACUATION_HELP = "EVACUATION_HELP"
    INFRASTRUCTURE_DAMAGE = "INFRASTRUCTURE_DAMAGE"
    OTHER = "OTHER"


class EmergencyReportRequest(BaseModel):
    category: EmergencyCategory
    message: str = Field(min_length=5, max_length=500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        trimmed = value.strip()

        if len(trimmed) < 5:
            raise ValueError("message must contain at least 5 non-whitespace characters")

        if len(trimmed) > 500:
            raise ValueError("message must not exceed 500 characters")

        return trimmed


class EmergencyReportResponse(BaseModel):
    status: Literal["received", "unavailable"]