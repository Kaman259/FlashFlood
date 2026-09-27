import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import emergency
from app.core.config import Settings
from app.main import app
from app.services.emergency_report_service import (
    EmergencyReportResult,
    STATUS_RECEIVED,
    STATUS_UNAVAILABLE,
)


class EmergencyReportsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        emergency._emergency_report_rate_limiter.reset()

    def enabled_settings(self):
        return Settings(
            _env_file=None,
            firestore_enabled=True,
            emergency_reporting_enabled=True,
            firebase_project_id="demo",
            firestore_emulator_host="127.0.0.1:8080",
        )

    def test_disabled_returns_safe_unavailable(self):
        with patch(
            "app.api.routes.emergency.settings",
            Settings(
                _env_file=None,
                firestore_enabled=False,
                emergency_reporting_enabled=False,
            ),
        ):
            response = self.client.post(
                "/api/emergency/reports",
                json={
                    "category": "FLOODING",
                    "message": "Flood water has entered the road.",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_valid_report_calls_service(self):
        with (
            patch(
                "app.api.routes.emergency.settings",
                self.enabled_settings(),
            ),
            patch(
                "app.api.routes.emergency.create_emergency_report",
                return_value=EmergencyReportResult(status=STATUS_RECEIVED),
            ) as service,
        ):
            response = self.client.post(
                "/api/emergency/reports",
                json={
                    "category": "MEDICAL",
                    "message": "Medical assistance is required.",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "received"})
        self.assertEqual(service.call_count, 1)

    def test_invalid_category_is_sanitized(self):
        response = self.client.post(
            "/api/emergency/reports",
            json={"category": "UNKNOWN", "message": "Valid message."},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {"detail": "Invalid emergency report request."},
        )

    def test_invalid_message_lengths_and_extra_fields_are_rejected(self):
        payloads = [
            {"category": "FLOODING", "message": "    "},
            {"category": "FLOODING", "message": "1234"},
            {"category": "FLOODING", "message": "x" * 501},
            {
                "category": "FLOODING",
                "message": "Valid message.",
                "latitude": 27.0,
            },
        ]

        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/emergency/reports",
                    json=payload,
                )
                self.assertEqual(response.status_code, 422)

    def test_rate_limit_is_bounded_per_framework_client(self):
        with (
            patch(
                "app.api.routes.emergency.settings",
                self.enabled_settings(),
            ),
            patch(
                "app.api.routes.emergency.create_emergency_report",
                return_value=EmergencyReportResult(status=STATUS_RECEIVED),
            ),
        ):
            for _ in range(emergency.REPORT_RATE_LIMIT):
                response = self.client.post(
                    "/api/emergency/reports",
                    json={
                        "category": "OTHER",
                        "message": "Valid prototype report.",
                    },
                )
                self.assertEqual(response.status_code, 200)

            limited = self.client.post(
                "/api/emergency/reports",
                json={
                    "category": "OTHER",
                    "message": "Valid prototype report.",
                },
            )

        self.assertEqual(limited.status_code, 429)

    def test_service_failure_returns_safe_unavailable(self):
        with (
            patch(
                "app.api.routes.emergency.settings",
                self.enabled_settings(),
            ),
            patch(
                "app.api.routes.emergency.create_emergency_report",
                return_value=EmergencyReportResult(status=STATUS_UNAVAILABLE),
            ),
        ):
            response = self.client.post(
                "/api/emergency/reports",
                json={
                    "category": "TRAPPED",
                    "message": "A person needs evacuation help.",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "unavailable"})


if __name__ == "__main__":
    unittest.main()