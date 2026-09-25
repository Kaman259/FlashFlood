import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.telemetry import TelemetryRecord, TelemetryScenario
from app.services.telemetry_service import (
    SCENARIO_RECORDS,
    SIMULATED_STATION_ID,
    telemetry_simulator,
    telemetry_to_risk_request,
)


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        telemetry_simulator.select_scenario(TelemetryScenario.NORMAL)

    def test_telemetry_model_validation(self):
        record = TelemetryRecord(
            timestamp="2026-09-01T08:00:00Z",
            station_id="TEST-STATION",
            river_level_m=1.5,
            river_change_m_per_hour=0.05,
            upstream_discharge_m3_per_s=120.0,
            scenario=TelemetryScenario.NORMAL,
        )

        self.assertEqual(record.station_id, "TEST-STATION")
        self.assertEqual(record.river_level_m, 1.5)
        self.assertEqual(record.upstream_discharge_m3_per_s, 120.0)

    def test_normal_scenario(self):
        record = telemetry_simulator.select_scenario(
            TelemetryScenario.NORMAL
        )

        self.assertEqual(record.river_level_m, 1.20)
        self.assertEqual(record.river_change_m_per_hour, 0.02)
        self.assertEqual(record.upstream_discharge_m3_per_s, 100.0)

    def test_watch_scenario(self):
        record = telemetry_simulator.select_scenario(
            TelemetryScenario.WATCH
        )

        self.assertEqual(record.river_level_m, 2.20)
        self.assertEqual(record.river_change_m_per_hour, 0.15)
        self.assertEqual(record.upstream_discharge_m3_per_s, 250.0)

    def test_moderate_surge_scenario(self):
        record = telemetry_simulator.select_scenario(
            TelemetryScenario.MODERATE_SURGE
        )

        self.assertEqual(record.river_level_m, 3.20)
        self.assertEqual(record.river_change_m_per_hour, 0.35)
        self.assertEqual(record.upstream_discharge_m3_per_s, 500.0)

    def test_critical_surge_scenario(self):
        record = telemetry_simulator.select_scenario(
            TelemetryScenario.CRITICAL_SURGE
        )

        self.assertEqual(record.river_level_m, 4.40)
        self.assertEqual(record.river_change_m_per_hour, 0.75)
        self.assertEqual(record.upstream_discharge_m3_per_s, 900.0)

    def test_fields_and_demo_source(self):
        record = SCENARIO_RECORDS[TelemetryScenario.NORMAL]

        self.assertEqual(record.station_id, SIMULATED_STATION_ID)
        self.assertEqual(
            record.data_source,
            "SIMULATED_DEMONSTRATION",
        )

        self.assertIsInstance(record.river_level_m, float)
        self.assertIsInstance(
            record.river_change_m_per_hour,
            float,
        )
        self.assertIsInstance(
            record.upstream_discharge_m3_per_s,
            float,
        )

    def test_scenario_output_is_deterministic(self):
        first = telemetry_simulator.select_scenario(
            TelemetryScenario.MODERATE_SURGE
        )

        second = telemetry_simulator.select_scenario(
            TelemetryScenario.MODERATE_SURGE
        )

        self.assertEqual(first, second)

    def test_invalid_values_are_rejected(self):
        invalid_cases = [
            {
                "river_level_m": -1.0,
                "river_change_m_per_hour": 0.0,
                "upstream_discharge_m3_per_s": 100.0,
            },
            {
                "river_level_m": 101.0,
                "river_change_m_per_hour": 0.0,
                "upstream_discharge_m3_per_s": 100.0,
            },
            {
                "river_level_m": 1.0,
                "river_change_m_per_hour": 21.0,
                "upstream_discharge_m3_per_s": 100.0,
            },
            {
                "river_level_m": 1.0,
                "river_change_m_per_hour": 0.0,
                "upstream_discharge_m3_per_s": -1.0,
            },
            {
                "river_level_m": 1.0,
                "river_change_m_per_hour": 0.0,
                "upstream_discharge_m3_per_s": 100001.0,
            },
        ]

        for values in invalid_cases:
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    TelemetryRecord(
                        timestamp="2026-09-01T08:00:00Z",
                        station_id="TEST-STATION",
                        scenario=TelemetryScenario.NORMAL,
                        **values,
                    )

    def test_empty_station_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            TelemetryRecord(
                timestamp="2026-09-01T08:00:00Z",
                station_id="",
                river_level_m=1.0,
                river_change_m_per_hour=0.0,
                upstream_discharge_m3_per_s=100.0,
                scenario=TelemetryScenario.NORMAL,
            )

    def test_latest_endpoint_returns_current_scenario(self):
        telemetry_simulator.select_scenario(
            TelemetryScenario.WATCH
        )

        response = self.client.get(
            "/api/telemetry/latest"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["scenario"],
            "watch",
        )
        self.assertEqual(
            response.json()["river_level_m"],
            2.2,
        )
        self.assertEqual(
            response.json()["upstream_discharge_m3_per_s"],
            250.0,
        )

    def test_demo_scenario_endpoint(self):
        response = self.client.get(
            "/api/telemetry/demo/critical-surge"
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(
            body["scenario"],
            "critical-surge",
        )
        self.assertEqual(
            body["river_level_m"],
            4.4,
        )
        self.assertEqual(
            body["river_change_m_per_hour"],
            0.75,
        )
        self.assertEqual(
            body["upstream_discharge_m3_per_s"],
            900.0,
        )

    def test_invalid_scenario_endpoint_is_rejected(self):
        response = self.client.get(
            "/api/telemetry/demo/not-a-scenario"
        )

        self.assertEqual(response.status_code, 422)

    def test_telemetry_to_risk_request_conversion(self):
        telemetry = telemetry_simulator.select_scenario(
            TelemetryScenario.MODERATE_SURGE
        )

        request = telemetry_to_risk_request(
            telemetry,
            live_rainfall_intensity_mm_per_hour=12.5,
            forecast_rainfall_intensity_mm_per_hour=35.0,
        )

        self.assertEqual(
            request.live_rainfall_intensity_mm_per_hour,
            12.5,
        )
        self.assertEqual(
            request.forecast_rainfall_intensity_mm_per_hour,
            35.0,
        )
        self.assertEqual(
            request.river_level_m,
            telemetry.river_level_m,
        )
        self.assertEqual(
            request.river_change_m_per_hour,
            telemetry.river_change_m_per_hour,
        )
        self.assertEqual(
            request.upstream_discharge_m3_per_s,
            telemetry.upstream_discharge_m3_per_s,
        )
        self.assertEqual(
            request.station_id,
            telemetry.station_id,
        )

if __name__ == "__main__":
    unittest.main()


