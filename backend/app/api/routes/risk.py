from fastapi import APIRouter

from app.models.risk import RiskAssessmentRequest, RiskAssessmentResponse
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
    return evaluate_risk(request)
