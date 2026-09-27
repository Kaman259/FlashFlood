import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.fcm_service import (
    FcmSendResult,
    STATUS_INITIALIZATION_ERROR,
    STATUS_NO_REGISTRATIONS,
    STATUS_PARTIAL_FAILURE,
)
from app.services.firestore_service import (
    PersistenceResult,
    STATUS_STORED,
)
from app.services.risk_communication_service import (
    RiskTransitionContext,
    handle_risk_communication,
)
from app.services.sms_simulator_service import (
    STATUS_UNAVAILABLE,
    TRIGGER_FCM_INITIALIZATION_FAILURE,
    TRIGGER_NO_FCM_REGISTRATIONS,
    simulate_red_sms_fallback,
)


class Stage12PolicyRegressionTests(unittest.TestCase):
    def settings(self):
        return Settings(
            _env_file=None,
            firestore_enabled=True,
            fcm_enabled=True,
            sms_simulator_enabled=True,
            emergency_reporting_enabled=True,
            firebase_project_id="demo-flashflood",
            firestore_emulator_host="127.0.0.1:8080",
        )

    def result(self, level=RiskLevel.RED):
        return RiskAssessmentResponse(
            risk_level=level,
            risk_score=99 if level == RiskLevel.RED else 62,
            reasons=["Test reason."],
            recommended_action="Test action.",
            warning_message="Test warning.",
        )

    def persisted(self):
        return PersistenceResult(
            attempted=True,
            persisted=True,
            status=STATUS_STORED,
        )

    def test_green_to_red_is_sms_fallback_eligible(self):
        with (
            patch(
                "app.services.fcm_service.send_risk_escalation_notification",
                return_value=FcmSendResult(
                    status=STATUS_NO_REGISTRATIONS,
                    attempted=True,
                    sent_count=0,
                ),
            ),
            patch(
                "app.services.sms_simulator_service.simulate_red_sms_fallback"
            ) as sms,
        ):
            handle_risk_communication(
                self.result(RiskLevel.RED),
                RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.GREEN,
                ),
                self.persisted(),
                self.settings(),
            )

        sms.assert_called_once()
        self.assertEqual(
            sms.call_args.args[1],
            TRIGGER_NO_FCM_REGISTRATIONS,
        )

    def test_no_fcm_registrations_maps_to_specific_sms_trigger(self):
        with (
            patch(
                "app.services.fcm_service.send_risk_escalation_notification",
                return_value=FcmSendResult(
                    status=STATUS_NO_REGISTRATIONS,
                    attempted=True,
                    sent_count=0,
                ),
            ),
            patch(
                "app.services.sms_simulator_service.simulate_red_sms_fallback"
            ) as sms,
        ):
            handle_risk_communication(
                self.result(),
                RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.ORANGE,
                ),
                self.persisted(),
                self.settings(),
            )

        self.assertEqual(
            sms.call_args.args[1],
            TRIGGER_NO_FCM_REGISTRATIONS,
        )

    def test_fcm_initialization_failure_maps_to_specific_sms_trigger(self):
        with (
            patch(
                "app.services.fcm_service.send_risk_escalation_notification",
                return_value=FcmSendResult(
                    status=STATUS_INITIALIZATION_ERROR,
                    attempted=True,
                    sent_count=0,
                ),
            ),
            patch(
                "app.services.sms_simulator_service.simulate_red_sms_fallback"
            ) as sms,
        ):
            handle_risk_communication(
                self.result(),
                RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.ORANGE,
                ),
                self.persisted(),
                self.settings(),
            )

        self.assertEqual(
            sms.call_args.args[1],
            TRIGGER_FCM_INITIALIZATION_FAILURE,
        )

    def test_partial_fcm_success_does_not_generate_sms(self):
        with (
            patch(
                "app.services.fcm_service.send_risk_escalation_notification",
                return_value=FcmSendResult(
                    status=STATUS_PARTIAL_FAILURE,
                    attempted=True,
                    sent_count=1,
                    failed_count=2,
                ),
            ),
            patch(
                "app.services.sms_simulator_service.simulate_red_sms_fallback"
            ) as sms,
        ):
            handle_risk_communication(
                self.result(),
                RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.ORANGE,
                ),
                self.persisted(),
                self.settings(),
            )

        sms.assert_not_called()

    def test_sms_firestore_failure_is_safe_result(self):
        with patch(
            "app.services.sms_simulator_service.get_firestore_client",
            side_effect=RuntimeError("private Firestore failure"),
        ):
            result = simulate_red_sms_fallback(
                self.result(),
                "FCM_SEND_FAILURE_FALLBACK",
                self.settings(),
            )

        self.assertEqual(result.status, STATUS_UNAVAILABLE)

    def test_emergency_api_rejects_identity_coordinate_and_status_fields(self):
        client = TestClient(app)

        for field, value in (
            ("latitude", 27.0),
            ("longitude", 95.0),
            ("name", "Example User"),
            ("email", "person@example.invalid"),
            ("phone", "0000000000"),
            ("status", "RESOLVED"),
            ("report_id", "client-controlled"),
        ):
            with self.subTest(field=field):
                response = client.post(
                    "/api/emergency/reports",
                    json={
                        "category": "FLOODING",
                        "message": "Flood water has entered the road.",
                        field: value,
                    },
                )

                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json(),
                    {
                        "detail":
                            "Invalid emergency report request."
                    },
                )


if __name__ == "__main__":
    unittest.main()