from datetime import datetime, timezone

from app.models.risk import RiskAssessmentRequest
from app.models.telemetry import TelemetryRecord, TelemetryScenario


SIMULATED_STATION_ID = "UPSTREAM-DEMO-01"


# SIMULATED / DEMONSTRATION DATA ONLY.
# These measurements are fixed for reproducible prototype demonstrations.
# They are not real observations and are not scientifically calibrated.
SCENARIO_RECORDS = {
    TelemetryScenario.NORMAL: TelemetryRecord(
        timestamp=datetime(
            2026, 9, 1, 8, 0, tzinfo=timezone.utc
        ),
        station_id=SIMULATED_STATION_ID,
        river_level_m=1.20,
        river_change_m_per_hour=0.02,
        upstream_discharge_m3_per_s=100.0,
        scenario=TelemetryScenario.NORMAL,
    ),
    TelemetryScenario.WATCH: TelemetryRecord(
        timestamp=datetime(
            2026, 9, 1, 8, 15, tzinfo=timezone.utc
        ),
        station_id=SIMULATED_STATION_ID,
        river_level_m=2.20,
        river_change_m_per_hour=0.15,
        upstream_discharge_m3_per_s=250.0,
        scenario=TelemetryScenario.WATCH,
    ),
    TelemetryScenario.MODERATE_SURGE: TelemetryRecord(
        timestamp=datetime(
            2026, 9, 1, 8, 30, tzinfo=timezone.utc
        ),
        station_id=SIMULATED_STATION_ID,
        river_level_m=3.20,
        river_change_m_per_hour=0.35,
        upstream_discharge_m3_per_s=500.0,
        scenario=TelemetryScenario.MODERATE_SURGE,
    ),
    TelemetryScenario.CRITICAL_SURGE: TelemetryRecord(
        timestamp=datetime(
            2026, 9, 1, 8, 45, tzinfo=timezone.utc
        ),
        station_id=SIMULATED_STATION_ID,
        river_level_m=4.40,
        river_change_m_per_hour=0.75,
        upstream_discharge_m3_per_s=900.0,
        scenario=TelemetryScenario.CRITICAL_SURGE,
    ),
}


class TelemetrySimulator:
    def __init__(self) -> None:
        self._current_scenario = TelemetryScenario.NORMAL

    def get_latest(self) -> TelemetryRecord:
        return SCENARIO_RECORDS[
            self._current_scenario
        ].model_copy(deep=True)

    def select_scenario(
        self,
        scenario: TelemetryScenario,
    ) -> TelemetryRecord:
        self._current_scenario = scenario
        return self.get_latest()


telemetry_simulator = TelemetrySimulator()


def telemetry_to_risk_request(
    telemetry: TelemetryRecord,
    rainfall_intensity_mm_per_hour: float,
) -> RiskAssessmentRequest:
    return RiskAssessmentRequest(
        rainfall_intensity_mm_per_hour=rainfall_intensity_mm_per_hour,
        river_level_m=telemetry.river_level_m,
        river_change_m_per_hour=telemetry.river_change_m_per_hour,
        station_id=telemetry.station_id,
    )
