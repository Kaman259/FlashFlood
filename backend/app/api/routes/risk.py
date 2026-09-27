from fastapi import APIRouter

from app.models.risk import RiskAssessmentRequest, RiskAssessmentResponse
from app.services.firestore_service import persist_risk_assessment
from app.services.risk_communication_service import (
    capture_previous_risk_level,
    handle_risk_communication,
)
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

    # Transition state is captured before persistence so repeated polling can
    # be deduplicated against authoritative persisted history.
    transition = capture_previous_risk_level()

    # Persistence and communication are best-effort and never alter risk output.
    persistence = persist_risk_assessment(request, result)

    handle_risk_communication(
        result=result,
        transition=transition,
        persistence=persistence,
    )

    return result