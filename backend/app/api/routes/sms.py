from fastapi import APIRouter

from app.models.sms import SmsEventResponse, SmsLatestResponse
from app.services.sms_simulator_service import (
    STATUS_DISABLED,
    STATUS_EMPTY,
    STATUS_SIMULATED,
    get_latest_simulated_sms,
)


router = APIRouter(
    prefix="/api/sms",
    tags=["SMS Simulator"],
)


@router.get(
    "/latest",
    response_model=SmsLatestResponse,
    summary="Get latest simulated SMS fallback event",
)
def get_latest_sms_endpoint() -> SmsLatestResponse:
    result = get_latest_simulated_sms()

    if result.status == STATUS_DISABLED:
        return SmsLatestResponse(status="unavailable")

    if result.status == STATUS_EMPTY:
        return SmsLatestResponse(status="empty")

    if result.status != STATUS_SIMULATED:
        return SmsLatestResponse(status="unavailable")

    return SmsLatestResponse(
        status="available",
        event=SmsEventResponse(
            created_at=result.created_at,
            risk_level=result.risk_level,
            recipient_reference=result.recipient_reference or "",
            message_body=result.message_body or "",
            delivery_status=result.delivery_status or "",
            trigger_type=result.trigger_type or "",
        ),
    )