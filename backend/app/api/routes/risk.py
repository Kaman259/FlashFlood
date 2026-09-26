from fastapi import APIRouter

from app.models.risk import RiskAssessmentRequest, RiskAssessmentResponse
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

    # Persistence is deliberately best-effort. A database problem must not
    # replace or alter an otherwise valid risk assessment.
    persist_risk_assessment(request, result)

    return result