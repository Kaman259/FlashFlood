from fastapi import APIRouter

from app.core.config import settings
from app.models.health import HealthResponse


router = APIRouter(
    prefix="/api",
    tags=["Health"],
)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API health",
)
def get_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )
