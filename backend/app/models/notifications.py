from typing import Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationRegistrationRequest(BaseModel):
    installation_id: str = Field(min_length=1, max_length=512)
    enabled: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("installation_id")
    @classmethod
    def validate_installation_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("installation_id must not be blank")

        if value != value.strip():
            raise ValueError(
                "installation_id must not contain surrounding whitespace"
            )

        if any(
            character.isspace()
            or unicodedata.category(character).startswith("C")
            for character in value
        ):
            raise ValueError(
                "installation_id must not contain whitespace or control characters"
            )

        return value


class NotificationRegistrationResponse(BaseModel):
    status: Literal[
        "registered",
        "disabled",
        "unavailable",
    ]