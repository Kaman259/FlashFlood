import unittest

from app.core.config import Settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.firestore_service import (
    PersistenceResult,
    STATUS_DISABLED as PERSISTENCE_DISABLED,
)
from app.services.risk_communication_service import (
    RiskTransitionContext,
    handle_risk_communication,
)
from app.services.sms_simulator_service import (
    SIMULATED_DELIVERY_STATUS,
    STATUS_EMPTY,
    STATUS_SIMULATED,
    TRIGGER_FCM_DISABLED,
    get_latest_simulated_sms,
    reset_local_sms_demo_state,
)


class LocalSmsPortfolioDemoTests(unittest.TestCase):
    def setUp(self):
        reset_local_sms_demo_state()

    def tearDown(self):
        reset_local_sms_demo_state()

    def settings(self):
        return Settings(
            _env_file=None,
            firestore_enabled=False,
            fcm_enabled=False,
            sms_simulator_enabled=True,
        )

    def result(self, level):
        scores = {
            RiskLevel.GREEN: 0,
            RiskLevel.YELLOW: 33,
            RiskLevel.ORANGE: 62,
            RiskLevel.RED: 99,
        }
        return RiskAssessmentResponse(
            risk_level=level,
            risk_score=scores[level],
            reasons=["portfolio demo"],
            recommended_action="Follow current safety guidance.",
            warning_message="Portfolio demo warning.",
        )

    def communicate(self, level):
        handle_risk_communication(
            result=self.result(level),
            transition=RiskTransitionContext(
                available=False,
                previous_level=None,
            ),
            persistence=PersistenceResult(
                attempted=False,
                persisted=False,
                status=PERSISTENCE_DISABLED,
            ),
            app_settings=self.settings(),
        )

    def test_local_mode_tracks_live_levels_but_only_records_red_escalation(self):
        self.communicate(RiskLevel.GREEN)
        self.assertEqual(
            get_latest_simulated_sms(self.settings()).status,
            STATUS_EMPTY,
        )

        self.communicate(RiskLevel.YELLOW)
        self.communicate(RiskLevel.ORANGE)
        self.assertEqual(
            get_latest_simulated_sms(self.settings()).status,
            STATUS_EMPTY,
        )

        self.communicate(RiskLevel.RED)
        latest = get_latest_simulated_sms(self.settings())

        self.assertEqual(latest.status, STATUS_SIMULATED)
        self.assertEqual(latest.risk_level, RiskLevel.RED)
        self.assertEqual(
            latest.delivery_status,
            SIMULATED_DELIVERY_STATUS,
        )
        self.assertEqual(
            latest.trigger_type,
            TRIGGER_FCM_DISABLED,
        )
        self.assertIsNotNone(latest.created_at)
        self.assertIn("RED - DANGER", latest.message_body or "")

    def test_repeated_red_does_not_create_a_second_local_event(self):
        self.communicate(RiskLevel.GREEN)
        self.communicate(RiskLevel.RED)

        first = get_latest_simulated_sms(self.settings())
        self.communicate(RiskLevel.RED)
        second = get_latest_simulated_sms(self.settings())

        self.assertEqual(first.status, STATUS_SIMULATED)
        self.assertEqual(second.status, STATUS_SIMULATED)
        self.assertEqual(first.created_at, second.created_at)
        self.assertEqual(first.message_body, second.message_body)


if __name__ == "__main__":
    unittest.main()
