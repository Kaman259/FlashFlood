import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.risk import RiskLevel
from app.services.fcm_service import (
    FcmSendResult,
    RiskTransitionContext,
    STATUS_SEND_ERROR,
)
from app.services.firestore_service import (
    PersistenceResult,
    STATUS_STORED,
)


class RiskNotificationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.payload = {
            "live_rainfall_intensity_mm_per_hour": 35.0,
            "forecast_rainfall_intensity_mm_per_hour": 10.0,
            "river_level_m": 3.2,
            "river_change_m_per_hour": 0.20,
            "upstream_discharge_m3_per_s": 100.0,
            "station_id": "DEMO-01",
        }

    def persisted(self):
        return PersistenceResult(
            attempted=True,
            persisted=True,
            status=STATUS_STORED,
        )

    def test_escalation_sends_after_successful_persistence(self):
        with (
            patch(
                "app.api.routes.risk.capture_previous_risk_level",
                return_value=RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.YELLOW,
                ),
            ),
            patch(
                "app.api.routes.risk.persist_risk_assessment",
                return_value=self.persisted(),
            ),
            patch(
                "app.api.routes.risk.send_risk_escalation_notification",
                return_value=FcmSendResult(
                    status="SENT",
                    sent_count=1,
                ),
            ) as mocked_send,
        ):
            response = self.client.post(
                "/api/risk/evaluate",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["risk_level"],
            "ORANGE",
        )
        mocked_send.assert_called_once()

    def test_same_level_does_not_send(self):
        with (
            patch(
                "app.api.routes.risk.capture_previous_risk_level",
                return_value=RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.ORANGE,
                ),
            ),
            patch(
                "app.api.routes.risk.persist_risk_assessment",
                return_value=self.persisted(),
            ),
            patch(
                "app.api.routes.risk.send_risk_escalation_notification"
            ) as mocked_send,
        ):
            response = self.client.post(
                "/api/risk/evaluate",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        mocked_send.assert_not_called()

    def test_lower_severity_does_not_send(self):
        with (
            patch(
                "app.api.routes.risk.capture_previous_risk_level",
                return_value=RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.RED,
                ),
            ),
            patch(
                "app.api.routes.risk.persist_risk_assessment",
                return_value=self.persisted(),
            ),
            patch(
                "app.api.routes.risk.send_risk_escalation_notification"
            ) as mocked_send,
        ):
            response = self.client.post(
                "/api/risk/evaluate",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        mocked_send.assert_not_called()

    def test_first_assessment_establishes_baseline_without_send(self):
        with (
            patch(
                "app.api.routes.risk.capture_previous_risk_level",
                return_value=RiskTransitionContext(
                    available=True,
                    previous_level=None,
                ),
            ),
            patch(
                "app.api.routes.risk.persist_risk_assessment",
                return_value=self.persisted(),
            ),
            patch(
                "app.api.routes.risk.send_risk_escalation_notification"
            ) as mocked_send,
        ):
            response = self.client.post(
                "/api/risk/evaluate",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        mocked_send.assert_not_called()

    def test_persistence_failure_prevents_notification_but_not_risk(self):
        with (
            patch(
                "app.api.routes.risk.capture_previous_risk_level",
                return_value=RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.YELLOW,
                ),
            ),
            patch(
                "app.api.routes.risk.persist_risk_assessment",
                return_value=PersistenceResult(
                    attempted=True,
                    persisted=False,
                    status="WRITE_ERROR",
                ),
            ),
            patch(
                "app.api.routes.risk.send_risk_escalation_notification"
            ) as mocked_send,
        ):
            response = self.client.post(
                "/api/risk/evaluate",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["risk_level"],
            "ORANGE",
        )
        mocked_send.assert_not_called()

    def test_fcm_failure_does_not_change_risk_result(self):
        with (
            patch(
                "app.api.routes.risk.capture_previous_risk_level",
                return_value=RiskTransitionContext(
                    available=True,
                    previous_level=RiskLevel.YELLOW,
                ),
            ),
            patch(
                "app.api.routes.risk.persist_risk_assessment",
                return_value=self.persisted(),
            ),
            patch(
                "app.api.routes.risk.send_risk_escalation_notification",
                return_value=FcmSendResult(
                    status=STATUS_SEND_ERROR,
                ),
            ),
        ):
            response = self.client.post(
                "/api/risk/evaluate",
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["risk_level"],
            "ORANGE",
        )
        self.assertEqual(
            response.json()["risk_score"],
            62,
        )


if __name__ == "__main__":
    unittest.main()