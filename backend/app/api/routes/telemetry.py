from fastapi import APIRouter

from app.models.telemetry import TelemetryRecord, TelemetryScenario
from app.services.telemetry_service import telemetry_simulator


router = APIRouter(
    prefix="/api/telemetry",
    tags=["Telemetry"],
)


@router.get(
    "/latest",
    response_model=TelemetryRecord,
    summary="Get latest simulated telemetry",
)
def get_latest_telemetry() -> TelemetryRecord:
    return telemetry_simulator.get_latest()


@router.get(
    "/demo/{scenario}",
    response_model=TelemetryRecord,
    summary="Select simulated telemetry scenario",
)
def select_demo_scenario(
    scenario: TelemetryScenario,
) -> TelemetryRecord:
    return telemetry_simulator.select_scenario(scenario)
