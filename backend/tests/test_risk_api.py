import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.risk import RiskAssessmentResponse, RiskLevel


class RiskEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def post_risk(
        self,
        live_rainfall: float,
        forecast_rainfall: float,
        river_level: float,
        river_change: float,
        discharge: float,
        station_id: str | None = "DEMO-01",
    ):
        payload = {
            "live_rainfall_intensity_mm_per_hour": live_rainfall,
            "forecast_rainfall_intensity_mm_per_hour": forecast_rainfall,
            "river_level_m": river_level,
            "river_change_m_per_hour": river_change,
            "upstream_discharge_m3_per_s": discharge,
        }

        if station_id is not None:
            payload["station_id"] = station_id

        return self.client.post(
            "/api/risk/evaluate",
            json=payload,
        )

    def test_valid_green_request(self):
        response = self.post_risk(
            10.0, 10.0, 1.0, 0.02, 100.0
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "GREEN")
        self.assertEqual(response.json()["risk_score"], 0)

    def test_forecast_rainfall_yellow_request(self):
        response = self.post_risk(
            10.0, 40.0, 1.0, 0.0, 100.0
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "YELLOW")
        self.assertEqual(response.json()["risk_score"], 25)

    def test_live_rainfall_orange_request(self):
        response = self.post_risk(
            35.0, 10.0, 1.0, 0.0, 100.0
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "ORANGE")
        self.assertEqual(response.json()["risk_score"], 50)

    def test_live_rainfall_red_request(self):
        response = self.post_risk(
            55.0, 10.0, 1.0, 0.0, 100.0
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "RED")
        self.assertEqual(response.json()["risk_score"], 75)

    def test_forecast_rainfall_boundaries(self):
        cases = [
            (30.00, "GREEN", 0),
            (30.01, "YELLOW", 25),
        ]

        for forecast, level, score in cases:
            with self.subTest(forecast=forecast):
                response = self.post_risk(
                    0.0, forecast, 0.0, 0.0, 0.0
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["risk_level"], level)
                self.assertEqual(response.json()["risk_score"], score)

    def test_live_rainfall_boundaries(self):
        cases = [
            (30.00, "GREEN", 0),
            (30.01, "ORANGE", 50),
            (50.00, "ORANGE", 50),
            (50.01, "RED", 75),
        ]

        for live, level, score in cases:
            with self.subTest(live=live):
                response = self.post_risk(
                    live, 0.0, 0.0, 0.0, 0.0
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["risk_level"], level)
                self.assertEqual(response.json()["risk_score"], score)

    def test_combined_rainfall_uses_more_severe_classification(self):
        cases = [
            (10.0, 40.0, "YELLOW", 25),
            (35.0, 40.0, "ORANGE", 50),
            (55.0, 40.0, "RED", 75),
            (35.0, 10.0, "ORANGE", 50),
            (50.0, 10.0, "ORANGE", 50),
        ]

        for live, forecast, level, score in cases:
            with self.subTest(live=live, forecast=forecast):
                response = self.post_risk(
                    live, forecast, 0.0, 0.0, 0.0
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["risk_level"], level)
                self.assertEqual(response.json()["risk_score"], score)

    def test_exact_river_level_boundaries(self):
        cases = [
            (2.0, "YELLOW", 25),
            (3.0, "ORANGE", 50),
            (4.0, "RED", 75),
        ]

        for river_level, level, score in cases:
            with self.subTest(river_level=river_level):
                response = self.post_risk(
                    0.0, 0.0, river_level, 0.0, 0.0
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["risk_level"], level)
                self.assertEqual(response.json()["risk_score"], score)

    def test_exact_river_change_boundaries(self):
        cases = [
            (0.10, "YELLOW", 25),
            (0.30, "ORANGE", 50),
            (0.60, "RED", 75),
        ]

        for river_change, level, score in cases:
            with self.subTest(river_change=river_change):
                response = self.post_risk(
                    0.0, 0.0, 0.0, river_change, 0.0
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["risk_level"], level)
                self.assertEqual(response.json()["risk_score"], score)

    def test_exact_discharge_boundaries(self):
        cases = [
            (200.0, "YELLOW", 25),
            (400.0, "ORANGE", 50),
            (800.0, "RED", 75),
        ]

        for discharge, level, score in cases:
            with self.subTest(discharge=discharge):
                response = self.post_risk(
                    0.0, 0.0, 0.0, 0.0, discharge
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["risk_level"], level)
                self.assertEqual(response.json()["risk_score"], score)

    def test_red_discharge_only_request(self):
        response = self.post_risk(
            0.0, 0.0, 1.0, 0.0, 900.0
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "RED")
        self.assertEqual(response.json()["risk_score"], 75)

    def test_missing_live_rainfall_is_rejected(self):
        response = self.client.post(
            "/api/risk/evaluate",
            json={
                "forecast_rainfall_intensity_mm_per_hour": 10.0,
                "river_level_m": 1.0,
                "river_change_m_per_hour": 0.0,
                "upstream_discharge_m3_per_s": 100.0,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_missing_forecast_rainfall_is_rejected(self):
        response = self.client.post(
            "/api/risk/evaluate",
            json={
                "live_rainfall_intensity_mm_per_hour": 10.0,
                "river_level_m": 1.0,
                "river_change_m_per_hour": 0.0,
                "upstream_discharge_m3_per_s": 100.0,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_negative_live_rainfall_is_rejected(self):
        response = self.post_risk(
            -1.0, 10.0, 1.0, 0.0, 100.0
        )

        self.assertEqual(response.status_code, 422)

    def test_negative_forecast_rainfall_is_rejected(self):
        response = self.post_risk(
            10.0, -1.0, 1.0, 0.0, 100.0
        )

        self.assertEqual(response.status_code, 422)

    def test_negative_river_level_is_rejected(self):
        response = self.post_risk(
            0.0, 0.0, -1.0, 0.0, 0.0
        )

        self.assertEqual(response.status_code, 422)

    def test_negative_discharge_is_rejected(self):
        response = self.post_risk(
            0.0, 0.0, 1.0, 0.0, -1.0
        )

        self.assertEqual(response.status_code, 422)

    def test_values_above_validation_limits_are_rejected(self):
        cases = [
            (501.0, 0.0, 1.0, 0.0, 0.0),
            (0.0, 501.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 101.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 21.0, 0.0),
            (0.0, 0.0, 1.0, -21.0, 0.0),
            (0.0, 0.0, 1.0, 0.0, 100001.0),
        ]

        for case in cases:
            with self.subTest(case=case):
                response = self.post_risk(*case)
                self.assertEqual(response.status_code, 422)

    def test_station_id_is_optional(self):
        response = self.post_risk(
            10.0,
            10.0,
            1.0,
            0.0,
            100.0,
            station_id=None,
        )

        self.assertEqual(response.status_code, 200)

    def test_response_schema(self):
        response = self.post_risk(
            35.0, 10.0, 3.2, 0.20, 100.0
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(
            set(body.keys()),
            {
                "risk_level",
                "risk_score",
                "reasons",
                "recommended_action",
                "warning_message",
            },
        )

    def test_endpoint_calls_existing_risk_service(self):
        service_result = RiskAssessmentResponse(
            risk_level=RiskLevel.YELLOW,
            risk_score=25,
            reasons=["Service call verified."],
            recommended_action="Test action.",
            warning_message="Test warning.",
        )

        with patch(
            "app.api.routes.risk.evaluate_risk",
            return_value=service_result,
        ) as mocked_service:
            response = self.post_risk(
                10.0,
                40.0,
                1.0,
                0.0,
                250.0,
            )

        self.assertEqual(response.status_code, 200)
        mocked_service.assert_called_once()

        request_argument = mocked_service.call_args.args[0]

        self.assertEqual(
            request_argument.live_rainfall_intensity_mm_per_hour,
            10.0,
        )
        self.assertEqual(
            request_argument.forecast_rainfall_intensity_mm_per_hour,
            40.0,
        )
        self.assertEqual(
            request_argument.upstream_discharge_m3_per_s,
            250.0,
        )


if __name__ == "__main__":
    unittest.main()
