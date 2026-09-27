from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.emergency import router as emergency_router
from app.api.routes.health import router as health_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.risk import router as risk_router
from app.api.routes.sms import router as sms_router
from app.api.routes.telemetry import router as telemetry_router
from app.api.routes.weather import router as weather_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    description="Backend for the FlashFlood educational flood-warning prototype.",
    version=settings.app_version,
)


@app.exception_handler(RequestValidationError)
async def sanitize_stage_validation_error(
    request: Request,
    error: RequestValidationError,
):
    if request.url.path == "/api/notifications/registration":
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Invalid notification registration request."
            },
        )

    if request.url.path == "/api/emergency/reports":
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Invalid emergency report request."
            },
        )

    return await request_validation_exception_handler(
        request,
        error,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health_router)
app.include_router(notifications_router)
app.include_router(sms_router)
app.include_router(emergency_router)
app.include_router(risk_router)
app.include_router(telemetry_router)
app.include_router(weather_router)