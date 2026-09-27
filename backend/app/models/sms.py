from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.risk import RiskLevel


class SmsEventResponse(BaseModel):
    created_at: datetime | None = None
    risk_level: RiskLevel
    recipient_reference: str
    message_body: str
    delivery_status: str
    trigger_type: str


class SmsLatestResponse(BaseModel):
    status: Literal["available", "empty", "unavailable"]
    event: SmsEventResponse | None = None