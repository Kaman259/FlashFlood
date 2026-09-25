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
        rainfall: float,
        river_level: float,
        river_change: float,
        station_id: str | None = "DEMO-01",
    ):
        payload = {
            "rainfall_intensity_mm_per_hour": rainfall,
            "river_level_m": river_level,
            "river_change_m_per_hour": river_change,
        }

        if station_id is not None:
            payload["station_id"] = station_id

        return self.client.post(
            "/api/risk/evaluate",
            json=payload,
        )

    def test_valid_green_request(self):
        response = self.post_risk(5.0, 1.0, 0.02)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "GREEN")
        self.assertEqual(response.json()["risk_score"], 0)

    def test_valid_yellow_request(self):
        response = self.post_risk(15.0, 1.0, 0.02)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "YELLOW")
        self.assertEqual(response.json()["risk_score"], 25)

    def test_valid_orange_request(self):
        response = self.post_risk(35.0, 3.2, 0.20)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "ORANGE")
        self.assertEqual(response.json()["risk_score"], 62)

    def test_valid_red_request(self):
        response = self.post_risk(50.0, 1.0, 0.02)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "RED")
        self.assertEqual(response.json()["risk_score"], 75)

    def test_exact_rainfall_boundaries(self):
        cases = [
            (15.0, "YELLOW", 25),
            (30.0, "ORANGE", 50),
            (50.0, "RED", 75),
        ]

        for rainfall, level, score in cases:
            with self.subTest(rainfall=rainfall):
                response = self.post_risk(rainfall, 0.0, 0.0)

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
                response = self.post_risk(0.0, river_level, 0.0)

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
                response = self.post_risk(0.0, 0.0, river_change)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["risk_level"], level)
                self.assertEqual(response.json()["risk_score"], score)

    def test_negative_rainfall_is_rejected(self):
        response = self.post_risk(-1.0, 1.0, 0.0)

        self.assertEqual(response.status_code, 422)

    def test_negative_river_level_is_rejected(self):
        response = self.post_risk(0.0, -1.0, 0.0)

        self.assertEqual(response.status_code, 422)

    def test_values_above_validation_limits_are_rejected(self):
        cases = [
            (501.0, 1.0, 0.0),
            (0.0, 101.0, 0.0),
            (0.0, 1.0, 21.0),
            (0.0, 1.0, -21.0),
        ]

        for case in cases:
            with self.subTest(case=case):
                response = self.post_risk(*case)
                self.assertEqual(response.status_code, 422)

    def test_station_id_is_optional(self):
        response = self.post_risk(
            5.0,
            1.0,
            0.0,
            station_id=None,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_level"], "GREEN")

    def test_response_schema(self):
        response = self.post_risk(35.0, 3.2, 0.20)

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

        self.assertIsInstance(body["risk_level"], str)
        self.assertIsInstance(body["risk_score"], int)
        self.assertIsInstance(body["reasons"], list)
        self.assertIsInstance(body["recommended_action"], str)
        self.assertIsInstance(body["warning_message"], str)

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
            response = self.post_risk(5.0, 1.0, 0.0)

        self.assertEqual(response.status_code, 200)
        mocked_service.assert_called_once()

        request_argument = mocked_service.call_args.args[0]

        self.assertEqual(
            request_argument.rainfall_intensity_mm_per_hour,
            5.0,
        )

        self.assertEqual(
            response.json(),
            service_result.model_dump(mode="json"),
        )


if __name__ == "__main__":
    unittest.main()
