from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.risk import router as risk_router
from app.api.routes.telemetry import router as telemetry_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    description="Backend for the FlashFlood educational flood-warning prototype.",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health_router)
app.include_router(risk_router)
app.include_router(telemetry_router)
