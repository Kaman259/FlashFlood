from fastapi import APIRouter

from app.models.risk import RiskAssessmentRequest, RiskAssessmentResponse
from app.services.fcm_service import (
    capture_previous_risk_level,
    is_risk_severity_increase,
    send_risk_escalation_notification,
)
from app.services.firestore_service import persist_risk_assessment
from app.services.risk_service import evaluate_risk


router = APIRouter(
    prefix="/api/risk",
    tags=["Risk"],
)


@router.post(
    "/evaluate",
    response_model=RiskAssessmentResponse,
    summary="Evaluate prototype flood risk",
)
def evaluate_risk_endpoint(
    request: RiskAssessmentRequest,
) -> RiskAssessmentResponse:
    result = evaluate_risk(request)

    # Capture the last persisted backend state before writing this assessment.
    # This prototype comparison is not transactionally deduplicated, so highly
    # concurrent evaluations could observe the same previous state.
    transition = capture_previous_risk_level()

    # Persistence remains best-effort and never changes the risk response.
    persistence = persist_risk_assessment(request, result)

    if (
        persistence.persisted
        and transition.available
        and is_risk_severity_increase(
            transition.previous_level,
            result.risk_level,
        )
    ):
        # FCM sending is also best-effort. A failed notification is not
        # retried by same-level polling because the risk assessment is already
        # persisted; a production system should use a durable outbox/retry path.
        send_risk_escalation_notification(result)

    return result