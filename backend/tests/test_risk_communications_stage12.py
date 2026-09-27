import unittest
from unittest.mock import patch

from app.core.config import Settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.fcm_service import (
    FcmSendResult,
    STATUS_DISABLED,
    STATUS_PARTIAL_FAILURE,
    STATUS_SEND_ERROR,
    STATUS_SENT,
)
from app.services.firestore_service import PersistenceResult, STATUS_STORED
from app.services.risk_communication_service import (
    RiskTransitionContext,
    handle_risk_communication,
)


class Stage12RiskCommunicationTests(unittest.TestCase):
    def result(self, level):
        return RiskAssessmentResponse(
            risk_level=level,
            risk_score=99 if level == RiskLevel.RED else 62,
            reasons=["demo"],
            recommended_action="Follow guidance.",
            warning_message="Demo.",
        )

    def persisted(self):
        return PersistenceResult(
            attempted=True,
            persisted=True,
            status=STATUS_STORED,
        )

    def settings(self):
        return Settings(
            _env_file=None,
            firestore_enabled=True,
            fcm_enabled=True,
            sms_simulator_enabled=True,
            firebase_project_id="demo",
            firestore_emulator_host="127.0.0.1:8080",
        )

    def run_case(self, previous, current, fcm_result):
        with (
            patch(
                "app.services.fcm_service.send_risk_escalation_notification",
                return_value=fcm_result,
            ) as fcm_send,
            patch(
                "app.services.sms_simulator_service.simulate_red_sms_fallback"
            ) as sms_send,
        ):
            handle_risk_communication(
                self.result(current),
                RiskTransitionContext(
                    available=True,
                    previous_level=previous,
                ),
                self.persisted(),
                self.settings(),
            )
        return fcm_send, sms_send

    def test_green_to_yellow_fcm_only(self):
        fcm, sms = self.run_case(
            RiskLevel.GREEN,
            RiskLevel.YELLOW,
            FcmSendResult(status=STATUS_SENT, attempted=True, sent_count=1),
        )
        fcm.assert_called_once()
        sms.assert_not_called()

    def test_yellow_to_orange_fcm_only(self):
        fcm, sms = self.run_case(
            RiskLevel.YELLOW,
            RiskLevel.ORANGE,
            FcmSendResult(status=STATUS_SEND_ERROR, attempted=True),
        )
        fcm.assert_called_once()
        sms.assert_not_called()

    def test_red_with_any_fcm_success_suppresses_sms(self):
        _fcm, sms = self.run_case(
            RiskLevel.ORANGE,
            RiskLevel.RED,
            FcmSendResult(
                status=STATUS_PARTIAL_FAILURE,
                attempted=True,
                sent_count=1,
                failed_count=2,
            ),
        )
        sms.assert_not_called()

    def test_red_with_zero_fcm_success_uses_sms_fallback(self):
        _fcm, sms = self.run_case(
            RiskLevel.ORANGE,
            RiskLevel.RED,
            FcmSendResult(
                status=STATUS_SEND_ERROR,
                attempted=True,
                sent_count=0,
                failed_count=1,
            ),
        )
        sms.assert_called_once()

    def test_fcm_disabled_red_uses_sms_fallback(self):
        _fcm, sms = self.run_case(
            RiskLevel.YELLOW,
            RiskLevel.RED,
            FcmSendResult(
                status=STATUS_DISABLED,
                attempted=False,
                sent_count=0,
            ),
        )
        sms.assert_called_once()

    def test_same_red_does_not_repeat(self):
        fcm, sms = self.run_case(
            RiskLevel.RED,
            RiskLevel.RED,
            FcmSendResult(status=STATUS_SENT, attempted=True, sent_count=1),
        )
        fcm.assert_not_called()
        sms.assert_not_called()

    def test_lower_severity_does_not_communicate(self):
        fcm, sms = self.run_case(
            RiskLevel.RED,
            RiskLevel.ORANGE,
            FcmSendResult(status=STATUS_SENT, attempted=True, sent_count=1),
        )
        fcm.assert_not_called()
        sms.assert_not_called()

    def test_first_assessment_is_baseline(self):
        fcm, sms = self.run_case(
            None,
            RiskLevel.RED,
            FcmSendResult(status=STATUS_DISABLED),
        )
        fcm.assert_not_called()
        sms.assert_not_called()


if __name__ == "__main__":
    unittest.main()