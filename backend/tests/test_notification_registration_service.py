import hashlib
import unittest
from unittest.mock import patch

from firebase_admin import firestore as admin_firestore

from app.core.config import Settings
from app.services.notification_registration_service import (
    NOTIFICATION_REGISTRATIONS_COLLECTION,
    STATUS_DISABLED,
    STATUS_REGISTERED,
    STATUS_UNAVAILABLE,
    _document_id_for_installation,
    register_notification_installation,
)


class FakeSnapshot:
    def __init__(self, exists: bool) -> None:
        self.exists = exists


class FakeDocument:
    def __init__(self, exists: bool = False) -> None:
        self.snapshot = FakeSnapshot(exists)
        self.set_calls = []

    def get(self):
        return self.snapshot

    def set(self, value, merge=False):
        self.set_calls.append((value, merge))


class FakeCollection:
    def __init__(self, document: FakeDocument) -> None:
        self.document_instance = document
        self.document_ids = []

    def document(self, document_id):
        self.document_ids.append(document_id)
        return self.document_instance


class FakeClient:
    def __init__(self, exists: bool = False) -> None:
        self.document = FakeDocument(exists=exists)
        self.collection_instance = FakeCollection(self.document)
        self.collection_names = []

    def collection(self, name):
        self.collection_names.append(name)
        return self.collection_instance


class NotificationRegistrationServiceTests(unittest.TestCase):
    def make_settings(
        self,
        *,
        fcm_enabled: bool = True,
        firestore_enabled: bool = True,
    ) -> Settings:
        return Settings(
            _env_file=None,
            fcm_enabled=fcm_enabled,
            firestore_enabled=firestore_enabled,
            firebase_project_id="demo-flashflood",
            firestore_emulator_host="127.0.0.1:8080",
        )

    def test_disabled_feature_does_not_use_firestore(self):
        with patch(
            "app.services.notification_registration_service.get_firestore_client"
        ) as mocked_client:
            result = register_notification_installation(
                "installation-123",
                True,
                app_settings=self.make_settings(
                    fcm_enabled=False,
                ),
            )

        self.assertEqual(result.status, STATUS_UNAVAILABLE)
        mocked_client.assert_not_called()

    def test_valid_registration_uses_correct_collection_and_hash(self):
        fake_client = FakeClient(exists=False)
        installation_id = "installation-123"

        with patch(
            "app.services.notification_registration_service.get_firestore_client",
            return_value=fake_client,
        ):
            result = register_notification_installation(
                installation_id,
                True,
                app_settings=self.make_settings(),
            )

        self.assertEqual(result.status, STATUS_REGISTERED)
        self.assertEqual(
            fake_client.collection_names,
            [NOTIFICATION_REGISTRATIONS_COLLECTION],
        )

        expected_hash = hashlib.sha256(
            installation_id.encode("utf-8")
        ).hexdigest()

        self.assertEqual(
            fake_client.collection_instance.document_ids,
            [expected_hash],
        )
        self.assertEqual(
            _document_id_for_installation(installation_id),
            expected_hash,
        )

    def test_new_registration_uses_server_timestamps(self):
        fake_client = FakeClient(exists=False)

        with patch(
            "app.services.notification_registration_service.get_firestore_client",
            return_value=fake_client,
        ):
            register_notification_installation(
                "installation-123",
                True,
                app_settings=self.make_settings(),
            )

        record, merge = fake_client.document.set_calls[0]

        self.assertTrue(merge)
        self.assertEqual(
            record["installation_id"],
            "installation-123",
        )
        self.assertTrue(record["enabled"])
        self.assertIs(
            record["created_at"],
            admin_firestore.SERVER_TIMESTAMP,
        )
        self.assertIs(
            record["updated_at"],
            admin_firestore.SERVER_TIMESTAMP,
        )

    def test_existing_registration_does_not_reset_created_at(self):
        fake_client = FakeClient(exists=True)

        with patch(
            "app.services.notification_registration_service.get_firestore_client",
            return_value=fake_client,
        ):
            register_notification_installation(
                "installation-123",
                True,
                app_settings=self.make_settings(),
            )

        record, _merge = fake_client.document.set_calls[0]

        self.assertNotIn("created_at", record)
        self.assertIn("updated_at", record)

    def test_disable_existing_registration_updates_same_document(self):
        fake_client = FakeClient(exists=True)

        with patch(
            "app.services.notification_registration_service.get_firestore_client",
            return_value=fake_client,
        ):
            result = register_notification_installation(
                "installation-123",
                False,
                app_settings=self.make_settings(),
            )

        self.assertEqual(result.status, STATUS_DISABLED)
        record, merge = fake_client.document.set_calls[0]
        self.assertTrue(merge)
        self.assertFalse(record["enabled"])
        self.assertIn("updated_at", record)

    def test_disable_missing_registration_does_not_create_document_data(self):
        fake_client = FakeClient(exists=False)

        with patch(
            "app.services.notification_registration_service.get_firestore_client",
            return_value=fake_client,
        ):
            result = register_notification_installation(
                "installation-123",
                False,
                app_settings=self.make_settings(),
            )

        self.assertEqual(result.status, STATUS_DISABLED)
        self.assertEqual(fake_client.document.set_calls, [])

    def test_registration_record_contains_no_location_fields(self):
        fake_client = FakeClient(exists=False)

        with patch(
            "app.services.notification_registration_service.get_firestore_client",
            return_value=fake_client,
        ):
            register_notification_installation(
                "installation-123",
                True,
                app_settings=self.make_settings(),
            )

        record = fake_client.document.set_calls[0][0]
        serialized = repr(record).lower()

        for forbidden in (
            "latitude",
            "longitude",
            "inside",
            "outside",
            "location_history",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_firestore_failure_is_safe_and_does_not_log_fid(self):
        installation_id = "installation-sensitive-123"

        with self.assertLogs(
            "app.services.notification_registration_service",
            level="WARNING",
        ) as captured_logs:
            with patch(
                "app.services.notification_registration_service.get_firestore_client",
                side_effect=RuntimeError(
                    "storage failure for installation-sensitive-123"
                ),
            ):
                result = register_notification_installation(
                    installation_id,
                    True,
                    app_settings=self.make_settings(),
                )

        self.assertEqual(result.status, STATUS_UNAVAILABLE)
        self.assertNotIn(
            installation_id,
            " ".join(captured_logs.output),
        )


if __name__ == "__main__":
    unittest.main()