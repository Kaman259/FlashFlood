import unittest
from unittest.mock import patch

from firebase_admin import firestore as admin_firestore

from app.core.config import Settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.sms_simulator_service import (
    SIMULATED_DELIVERY_STATUS,
    SIMULATED_RECIPIENT,
    SMS_MESSAGES_COLLECTION,
    STATUS_DISABLED,
    STATUS_SIMULATED,
    TRIGGER_FCM_DISABLED,
    simulate_red_sms_fallback,
)


class FakeDocument:
    def __init__(self):
        self.set_calls = []

    def set(self, value):
        self.set_calls.append(value)


class FakeCollection:
    def __init__(self):
        self.document_instance = FakeDocument()

    def document(self):
        return self.document_instance


class FakeClient:
    def __init__(self):
        self.collection_names = []
        self.collection_instance = FakeCollection()

    def collection(self, name):
        self.collection_names.append(name)
        return self.collection_instance


class SmsSimulatorServiceTests(unittest.TestCase):
    def settings(self, enabled=True):
        return Settings(
            _env_file=None,
            firestore_enabled=True,
            sms_simulator_enabled=enabled,
            firebase_project_id="demo",
            firestore_emulator_host="127.0.0.1:8080",
        )

    def result(self, level=RiskLevel.RED):
        return RiskAssessmentResponse(
            risk_level=level,
            risk_score=99 if level == RiskLevel.RED else 62,
            reasons=["demo"],
            recommended_action="Follow guidance.",
            warning_message="Demo warning.",
        )

    def test_disabled_mode_does_not_use_firestore(self):
        with patch(
            "app.services.sms_simulator_service.get_firestore_client"
        ) as client:
            result = simulate_red_sms_fallback(
                self.result(),
                TRIGGER_FCM_DISABLED,
                self.settings(enabled=False),
            )

        self.assertEqual(result.status, STATUS_DISABLED)
        client.assert_not_called()

    def test_red_fallback_persists_server_controlled_record(self):
        client = FakeClient()

        with patch(
            "app.services.sms_simulator_service.get_firestore_client",
            return_value=client,
        ):
            result = simulate_red_sms_fallback(
                self.result(),
                TRIGGER_FCM_DISABLED,
                self.settings(),
            )

        self.assertEqual(result.status, STATUS_SIMULATED)
        self.assertEqual(client.collection_names, [SMS_MESSAGES_COLLECTION])
        record = client.collection_instance.document_instance.set_calls[0]
        self.assertIs(record["created_at"], admin_firestore.SERVER_TIMESTAMP)
        self.assertEqual(record["risk_level"], "RED")
        self.assertEqual(record["recipient_reference"], SIMULATED_RECIPIENT)
        self.assertEqual(record["delivery_status"], SIMULATED_DELIVERY_STATUS)
        self.assertEqual(record["trigger_type"], TRIGGER_FCM_DISABLED)
        serialized = repr(record).lower()
        for forbidden in ("latitude", "longitude", "phone", "account_sid"):
            self.assertNotIn(forbidden, serialized)

    def test_non_red_does_not_simulate(self):
        with patch(
            "app.services.sms_simulator_service.get_firestore_client"
        ) as client:
            result = simulate_red_sms_fallback(
                self.result(RiskLevel.ORANGE),
                TRIGGER_FCM_DISABLED,
                self.settings(),
            )

        self.assertEqual(result.status, STATUS_DISABLED)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()