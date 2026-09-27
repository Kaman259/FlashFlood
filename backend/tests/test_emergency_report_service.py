import unittest
from unittest.mock import patch

from firebase_admin import firestore as admin_firestore

from app.core.config import Settings
from app.models.emergency import EmergencyReportRequest
from app.services.emergency_report_service import (
    EMERGENCY_REPORTS_COLLECTION,
    STATUS_RECEIVED,
    STATUS_UNAVAILABLE,
    create_emergency_report,
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


class EmergencyReportServiceTests(unittest.TestCase):
    def settings(self, enabled=True):
        return Settings(
            _env_file=None,
            firestore_enabled=True,
            emergency_reporting_enabled=enabled,
            firebase_project_id="demo",
            firestore_emulator_host="127.0.0.1:8080",
        )

    def report(self):
        return EmergencyReportRequest(
            category="FLOODING",
            message="Flood water has entered the road.",
        )

    def test_disabled_mode_does_not_use_firestore(self):
        with patch(
            "app.services.emergency_report_service.get_firestore_client"
        ) as client:
            result = create_emergency_report(
                self.report(),
                self.settings(enabled=False),
            )

        self.assertEqual(result.status, STATUS_UNAVAILABLE)
        client.assert_not_called()

    def test_valid_report_uses_narrow_collection_and_received_status(self):
        client = FakeClient()

        with patch(
            "app.services.emergency_report_service.get_firestore_client",
            return_value=client,
        ):
            result = create_emergency_report(
                self.report(),
                self.settings(),
            )

        self.assertEqual(result.status, STATUS_RECEIVED)
        self.assertEqual(client.collection_names, [EMERGENCY_REPORTS_COLLECTION])
        record = client.collection_instance.document_instance.set_calls[0]
        self.assertIs(record["created_at"], admin_firestore.SERVER_TIMESTAMP)
        self.assertEqual(record["category"], "FLOODING")
        self.assertEqual(record["status"], "RECEIVED")
        self.assertEqual(record["message"], "Flood water has entered the road.")
        serialized = repr(record).lower()
        for forbidden in (
            "latitude",
            "longitude",
            "phone",
            "email",
            "user_id",
            "location_history",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_firestore_failure_is_safe(self):
        with patch(
            "app.services.emergency_report_service.get_firestore_client",
            side_effect=RuntimeError("private storage detail"),
        ):
            result = create_emergency_report(
                self.report(),
                self.settings(),
            )

        self.assertEqual(result.status, STATUS_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()