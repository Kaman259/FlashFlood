import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import notifications
from app.core.config import Settings
from app.main import app
from app.services.notification_registration_service import (
    NotificationRegistrationResult,
    STATUS_REGISTERED,
)


class NotificationRegistrationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        notifications._registration_rate_limiter.reset()

    def enabled_settings(self):
        return Settings(
            _env_file=None,
            fcm_enabled=True,
            firestore_enabled=True,
            firebase_project_id="demo-flashflood",
            firestore_emulator_host="127.0.0.1:8080",
        )

    def test_fcm_disabled_returns_safe_unavailable_response(self):
        disabled = Settings(
            _env_file=None,
            fcm_enabled=False,
            firestore_enabled=False,
        )

        with patch(
            "app.api.routes.notifications.settings",
            disabled,
        ):
            response = self.client.post(
                "/api/notifications/registration",
                json={
                    "installation_id": "installation-123",
                    "enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "unavailable"},
        )

    def test_valid_registration_calls_narrow_service(self):
        with (
            patch(
                "app.api.routes.notifications.settings",
                self.enabled_settings(),
            ),
            patch(
                "app.api.routes.notifications.register_notification_installation",
                return_value=NotificationRegistrationResult(
                    status=STATUS_REGISTERED,
                ),
            ) as mocked_registration,
        ):
            response = self.client.post(
                "/api/notifications/registration",
                json={
                    "installation_id": "installation-123",
                    "enabled": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "registered"},
        )
        mocked_registration.assert_called_once_with(
            installation_id="installation-123",
            enabled=True,
        )

    def test_empty_installation_id_is_rejected(self):
        response = self.client.post(
            "/api/notifications/registration",
            json={
                "installation_id": "",
                "enabled": True,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_whitespace_installation_id_is_rejected(self):
        response = self.client.post(
            "/api/notifications/registration",
            json={
                "installation_id": "   ",
                "enabled": True,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_oversized_installation_id_is_rejected(self):
        response = self.client.post(
            "/api/notifications/registration",
            json={
                "installation_id": "x" * 513,
                "enabled": True,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_arbitrary_notification_fields_are_rejected_without_echoing_fid(self):
        installation_id = "installation-sensitive-123"

        response = self.client.post(
            "/api/notifications/registration",
            json={
                "installation_id": installation_id,
                "enabled": True,
                "title": "Not allowed",
                "latitude": 27.0,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {
                "detail": "Invalid notification registration request."
            },
        )
        self.assertNotIn(installation_id, response.text)

    def test_rate_limit_is_applied_per_framework_client_ip(self):
        with (
            patch(
                "app.api.routes.notifications.settings",
                self.enabled_settings(),
            ),
            patch(
                "app.api.routes.notifications.register_notification_installation",
                return_value=NotificationRegistrationResult(
                    status=STATUS_REGISTERED,
                ),
            ),
        ):
            for _ in range(
                notifications.REGISTRATION_RATE_LIMIT
            ):
                response = self.client.post(
                    "/api/notifications/registration",
                    json={
                        "installation_id": "installation-123",
                        "enabled": True,
                    },
                )
                self.assertEqual(response.status_code, 200)

            limited = self.client.post(
                "/api/notifications/registration",
                json={
                    "installation_id": "installation-123",
                    "enabled": True,
                },
            )

        self.assertEqual(limited.status_code, 429)


if __name__ == "__main__":
    unittest.main()