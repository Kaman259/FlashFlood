import unittest
from unittest.mock import MagicMock, patch

from firebase_admin import messaging

from app.core.config import Settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.fcm_service import (
    STATUS_DISABLED,
    STATUS_INITIALIZATION_ERROR,
    STATUS_NO_REGISTRATIONS,
    STATUS_PARTIAL_FAILURE,
    STATUS_SEND_ERROR,
    STATUS_SENT,
    RiskTransitionContext,
    build_risk_notification,
    capture_previous_risk_level,
    is_risk_severity_increase,
    send_risk_escalation_notification,
)


class FakeSendResponse:
    def __init__(self, success=True, exception=None):
        self.success = success
        self.exception = exception


class FakeBatchResponse:
    def __init__(self, responses):
        self.responses = responses
        self.success_count = sum(
            1 for response in responses if response.success
        )
        self.failure_count = (
            len(responses) - self.success_count
        )


class FakeRiskDocument:
    def __init__(self, risk_level):
        self.risk_level = risk_level

    def to_dict(self):
        return {"risk_level": self.risk_level}


class FakeRiskQuery:
    def __init__(self, documents):
        self.documents = documents

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, _value):
        return self

    def stream(self):
        return iter(self.documents)


class FakeRiskClient:
    def __init__(self, documents):
        self.documents = documents

    def collection(self, _name):
        return FakeRiskQuery(self.documents)


class FcmServiceTests(unittest.TestCase):
    def make_settings(
        self,
        *,
        fcm_enabled=True,
        firestore_enabled=True,
    ):
        return Settings(
            _env_file=None,
            fcm_enabled=fcm_enabled,
            firestore_enabled=firestore_enabled,
            firebase_project_id="demo-flashflood",
            firestore_emulator_host=None,
        )

    def make_result(self, level=RiskLevel.ORANGE):
        return RiskAssessmentResponse(
            risk_level=level,
            risk_score=50,
            reasons=["Test reason."],
            recommended_action="Test action.",
            warning_message="Test warning.",
        )

    def test_fcm_disabled_does_not_access_registrations(self):
        with patch(
            "app.services.fcm_service.get_enabled_installation_ids"
        ) as mocked_registrations:
            result = send_risk_escalation_notification(
                self.make_result(),
                app_settings=self.make_settings(
                    fcm_enabled=False,
                ),
            )

        self.assertEqual(result.status, STATUS_DISABLED)
        mocked_registrations.assert_not_called()

    def test_no_registrations_skips_firebase_initialization(self):
        with (
            patch(
                "app.services.fcm_service.get_enabled_installation_ids",
                return_value=[],
            ),
            patch(
                "app.services.fcm_service.get_real_firebase_app"
            ) as mocked_app,
        ):
            result = send_risk_escalation_notification(
                self.make_result(),
                app_settings=self.make_settings(),
            )

        self.assertEqual(
            result.status,
            STATUS_NO_REGISTRATIONS,
        )
        mocked_app.assert_not_called()

    def test_successful_fid_send_uses_fids_not_deprecated_tokens(self):
        fake_batch = FakeBatchResponse(
            [
                FakeSendResponse(success=True),
                FakeSendResponse(success=True),
            ]
        )
        captured_messages = []

        def fake_send(message, app=None):
            captured_messages.append(message)
            return fake_batch

        with (
            patch(
                "app.services.fcm_service.get_enabled_installation_ids",
                return_value=["fid-1", "fid-2"],
            ),
            patch(
                "app.services.fcm_service.get_real_firebase_app",
                return_value=object(),
            ),
            patch(
                "app.services.fcm_service.messaging.send_each_for_multicast",
                side_effect=fake_send,
            ),
        ):
            result = send_risk_escalation_notification(
                self.make_result(),
                app_settings=self.make_settings(),
            )

        self.assertEqual(result.status, STATUS_SENT)
        self.assertEqual(result.sent_count, 2)
        self.assertEqual(result.failed_count, 0)
        self.assertEqual(len(captured_messages), 1)
        self.assertEqual(
            captured_messages[0].fids,
            ["fid-1", "fid-2"],
        )
        self.assertFalse(captured_messages[0].tokens)

    def test_initialization_failure_is_safe(self):
        with (
            patch(
                "app.services.fcm_service.get_enabled_installation_ids",
                return_value=["fid-1"],
            ),
            patch(
                "app.services.fcm_service.get_real_firebase_app",
                side_effect=RuntimeError(
                    "private_key=DO_NOT_EXPOSE"
                ),
            ),
        ):
            result = send_risk_escalation_notification(
                self.make_result(),
                app_settings=self.make_settings(),
            )

        self.assertEqual(
            result.status,
            STATUS_INITIALIZATION_ERROR,
        )

    def test_send_failure_is_safe(self):
        with (
            patch(
                "app.services.fcm_service.get_enabled_installation_ids",
                return_value=["fid-1"],
            ),
            patch(
                "app.services.fcm_service.get_real_firebase_app",
                return_value=object(),
            ),
            patch(
                "app.services.fcm_service.messaging.send_each_for_multicast",
                side_effect=RuntimeError("FCM unavailable"),
            ),
        ):
            result = send_risk_escalation_notification(
                self.make_result(),
                app_settings=self.make_settings(),
            )

        self.assertEqual(result.status, STATUS_SEND_ERROR)

    def test_unregistered_fid_is_disabled_without_logging_fid(self):
        unregistered = messaging.UnregisteredError(
            "unregistered"
        )
        fake_batch = FakeBatchResponse(
            [
                FakeSendResponse(
                    success=False,
                    exception=unregistered,
                ),
                FakeSendResponse(success=True),
            ]
        )

        with (
            patch(
                "app.services.fcm_service.get_enabled_installation_ids",
                return_value=["fid-old", "fid-good"],
            ),
            patch(
                "app.services.fcm_service.get_real_firebase_app",
                return_value=object(),
            ),
            patch(
                "app.services.fcm_service.messaging.send_each_for_multicast",
                return_value=fake_batch,
            ),
            patch(
                "app.services.fcm_service.disable_notification_installations"
            ) as mocked_disable,
        ):
            result = send_risk_escalation_notification(
                self.make_result(),
                app_settings=self.make_settings(),
            )

        self.assertEqual(
            result.status,
            STATUS_PARTIAL_FAILURE,
        )
        mocked_disable.assert_called_once_with(
            ["fid-old"],
            self.make_settings(),
        )

    def test_notification_content_is_server_controlled(self):
        result = self.make_result(RiskLevel.RED)
        notification = build_risk_notification(result)

        self.assertEqual(
            notification.title,
            "FlashFlood Alert",
        )
        self.assertIn("RED - DANGER", notification.body)
        self.assertNotIn("critical-surge", notification.body)

    def test_severity_increase_policy(self):
        self.assertTrue(
            is_risk_severity_increase(
                RiskLevel.GREEN,
                RiskLevel.YELLOW,
            )
        )
        self.assertTrue(
            is_risk_severity_increase(
                RiskLevel.YELLOW,
                RiskLevel.ORANGE,
            )
        )
        self.assertTrue(
            is_risk_severity_increase(
                RiskLevel.ORANGE,
                RiskLevel.RED,
            )
        )
        self.assertFalse(
            is_risk_severity_increase(
                RiskLevel.ORANGE,
                RiskLevel.ORANGE,
            )
        )
        self.assertFalse(
            is_risk_severity_increase(
                RiskLevel.RED,
                RiskLevel.YELLOW,
            )
        )
        self.assertFalse(
            is_risk_severity_increase(
                None,
                RiskLevel.RED,
            )
        )

    def test_first_persisted_assessment_is_baseline(self):
        with patch(
            "app.services.risk_communication_service.get_firestore_client",
            return_value=FakeRiskClient([]),
        ):
            context = capture_previous_risk_level(
                self.make_settings()
            )

        self.assertEqual(
            context,
            RiskTransitionContext(
                available=True,
                previous_level=None,
            ),
        )

    def test_previous_risk_level_is_read_from_persisted_backend_state(self):
        with patch(
            "app.services.risk_communication_service.get_firestore_client",
            return_value=FakeRiskClient(
                [FakeRiskDocument("YELLOW")]
            ),
        ):
            context = capture_previous_risk_level(
                self.make_settings()
            )

        self.assertTrue(context.available)
        self.assertEqual(
            context.previous_level,
            RiskLevel.YELLOW,
        )


if __name__ == "__main__":
    unittest.main()