import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from firebase_admin import firestore as admin_firestore

from app.core.config import Settings
from app.main import app
from app.models.risk import RiskAssessmentRequest, RiskAssessmentResponse, RiskLevel
from app.services.firestore_service import (
    PersistenceResult,
    RISK_ASSESSMENTS_COLLECTION,
    STATUS_DISABLED,
    STATUS_INITIALIZATION_ERROR,
    STATUS_STORED,
    STATUS_WRITE_ERROR,
    persist_risk_assessment,
)
from app.services.risk_service import evaluate_risk


class FakeDocument:
    def __init__(self, fail_write: bool = False) -> None:
        self.fail_write = fail_write
        self.written = None

    def set(self, value) -> None:
        if self.fail_write:
            raise RuntimeError("simulated Firestore write failure")

        self.written = value


class FakeCollection:
    def __init__(self, name: str, document: FakeDocument) -> None:
        self.name = name
        self.document_instance = document
        self.document_calls = 0

    def document(self):
        self.document_calls += 1
        return self.document_instance


class FakeFirestoreClient:
    def __init__(self, fail_write: bool = False) -> None:
        self.document = FakeDocument(fail_write=fail_write)
        self.collection_instance = None
        self.collection_names = []

    def collection(self, name: str):
        self.collection_names.append(name)
        self.collection_instance = FakeCollection(name, self.document)
        return self.collection_instance


class FirestorePersistenceTests(unittest.TestCase):
    def make_settings(
        self,
        *,
        enabled: bool = True,
        project_id: str | None = "demo-flashflood",
        emulator_host: str | None = "127.0.0.1:8080",
    ) -> Settings:
        return Settings(
            _env_file=None,
            firestore_enabled=enabled,
            firebase_project_id=project_id,
            google_application_credentials=None,
            firestore_emulator_host=emulator_host,
        )

    def make_request(
        self,
        station_id: str | None = "UPSTREAM-DEMO-01",
    ) -> RiskAssessmentRequest:
        return RiskAssessmentRequest(
            live_rainfall_intensity_mm_per_hour=35.0,
            forecast_rainfall_intensity_mm_per_hour=40.0,
            river_level_m=3.2,
            river_change_m_per_hour=0.35,
            upstream_discharge_m3_per_s=500.0,
            station_id=station_id,
        )

    def make_result(
        self,
        request: RiskAssessmentRequest | None = None,
    ) -> RiskAssessmentResponse:
        return evaluate_risk(request or self.make_request())

    def test_firestore_disabled_does_not_initialize_or_write(self):
        request = self.make_request()
        result = self.make_result(request)
        settings = self.make_settings(enabled=False)

        with patch(
            "app.services.firestore_service._get_firestore_client"
        ) as mocked_client:
            persistence = persist_risk_assessment(
                request,
                result,
                app_settings=settings,
            )

        self.assertEqual(persistence.status, STATUS_DISABLED)
        self.assertFalse(persistence.attempted)
        self.assertFalse(persistence.persisted)
        mocked_client.assert_not_called()

    def test_enabled_persistence_uses_only_risk_assessments_collection(self):
        request = self.make_request()
        result = self.make_result(request)
        settings = self.make_settings()
        fake_client = FakeFirestoreClient()

        with patch(
            "app.services.firestore_service._get_firestore_client",
            return_value=fake_client,
        ):
            persistence = persist_risk_assessment(
                request,
                result,
                app_settings=settings,
            )

        self.assertEqual(persistence.status, STATUS_STORED)
        self.assertTrue(persistence.attempted)
        self.assertTrue(persistence.persisted)
        self.assertEqual(
            fake_client.collection_names,
            [RISK_ASSESSMENTS_COLLECTION],
        )
        self.assertEqual(
            fake_client.collection_instance.document_calls,
            1,
        )

    def test_persisted_record_contains_expected_validated_fields(self):
        request = self.make_request()
        result = self.make_result(request)
        settings = self.make_settings()
        fake_client = FakeFirestoreClient()

        with patch(
            "app.services.firestore_service._get_firestore_client",
            return_value=fake_client,
        ):
            persist_risk_assessment(
                request,
                result,
                app_settings=settings,
            )

        record = fake_client.document.written

        self.assertEqual(record["risk_level"], result.risk_level.value)
        self.assertEqual(record["risk_score"], result.risk_score)
        self.assertEqual(record["reasons"], result.reasons)
        self.assertEqual(
            record["recommended_action"],
            result.recommended_action,
        )
        self.assertEqual(record["warning_message"], result.warning_message)
        self.assertEqual(
            record["inputs"]["live_rainfall_intensity_mm_per_hour"],
            request.live_rainfall_intensity_mm_per_hour,
        )
        self.assertEqual(
            record["inputs"]["forecast_rainfall_intensity_mm_per_hour"],
            request.forecast_rainfall_intensity_mm_per_hour,
        )
        self.assertEqual(
            record["inputs"]["river_level_m"],
            request.river_level_m,
        )
        self.assertEqual(
            record["inputs"]["river_change_m_per_hour"],
            request.river_change_m_per_hour,
        )
        self.assertEqual(
            record["inputs"]["upstream_discharge_m3_per_s"],
            request.upstream_discharge_m3_per_s,
        )
        self.assertEqual(record["inputs"]["station_id"], request.station_id)

    def test_created_at_uses_firestore_server_timestamp(self):
        request = self.make_request()
        result = self.make_result(request)
        fake_client = FakeFirestoreClient()

        with patch(
            "app.services.firestore_service._get_firestore_client",
            return_value=fake_client,
        ):
            persist_risk_assessment(
                request,
                result,
                app_settings=self.make_settings(),
            )

        self.assertIs(
            fake_client.document.written["created_at"],
            admin_firestore.SERVER_TIMESTAMP,
        )

    def test_optional_station_id_is_preserved_as_none(self):
        request = self.make_request(station_id=None)
        result = self.make_result(request)
        fake_client = FakeFirestoreClient()

        with patch(
            "app.services.firestore_service._get_firestore_client",
            return_value=fake_client,
        ):
            persist_risk_assessment(
                request,
                result,
                app_settings=self.make_settings(),
            )

        self.assertIsNone(fake_client.document.written["inputs"]["station_id"])

    def test_missing_project_id_is_handled_without_write(self):
        request = self.make_request()
        result = self.make_result(request)

        persistence = persist_risk_assessment(
            request,
            result,
            app_settings=self.make_settings(project_id=None),
        )

        self.assertEqual(
            persistence.status,
            STATUS_INITIALIZATION_ERROR,
        )
        self.assertTrue(persistence.attempted)
        self.assertFalse(persistence.persisted)

    def test_invalid_emulator_host_is_handled_without_write(self):
        request = self.make_request()
        result = self.make_result(request)

        persistence = persist_risk_assessment(
            request,
            result,
            app_settings=self.make_settings(
                emulator_host="http://127.0.0.1:8080"
            ),
        )

        self.assertEqual(
            persistence.status,
            STATUS_INITIALIZATION_ERROR,
        )
        self.assertFalse(persistence.persisted)

    def test_initialization_failure_is_safe_and_does_not_expose_exception(self):
        request = self.make_request()
        result = self.make_result(request)
        fake_secret = "private_key=DO_NOT_EXPOSE"

        with self.assertLogs(
            "app.services.firestore_service",
            level="WARNING",
        ) as captured_logs:
            with patch(
                "app.services.firestore_service._get_firestore_client",
                side_effect=RuntimeError(fake_secret),
            ):
                persistence = persist_risk_assessment(
                    request,
                    result,
                    app_settings=self.make_settings(),
                )

        self.assertEqual(
            persistence.status,
            STATUS_INITIALIZATION_ERROR,
        )
        self.assertFalse(persistence.persisted)

        logs = " ".join(captured_logs.output)
        self.assertIn("RuntimeError", logs)
        self.assertNotIn(fake_secret, logs)

    def test_write_failure_is_safe(self):
        request = self.make_request()
        result = self.make_result(request)
        fake_client = FakeFirestoreClient(fail_write=True)

        with patch(
            "app.services.firestore_service._get_firestore_client",
            return_value=fake_client,
        ):
            persistence = persist_risk_assessment(
                request,
                result,
                app_settings=self.make_settings(),
            )

        self.assertEqual(persistence.status, STATUS_WRITE_ERROR)
        self.assertTrue(persistence.attempted)
        self.assertFalse(persistence.persisted)

    def test_persisted_record_contains_no_browser_location_fields(self):
        request = self.make_request()
        result = self.make_result(request)
        fake_client = FakeFirestoreClient()

        with patch(
            "app.services.firestore_service._get_firestore_client",
            return_value=fake_client,
        ):
            persist_risk_assessment(
                request,
                result,
                app_settings=self.make_settings(),
            )

        serialized_keys = repr(fake_client.document.written).lower()

        for forbidden in (
            "latitude",
            "longitude",
            "browser_location",
            "inside_affected_area",
            "outside_affected_area",
            "location_history",
        ):
            self.assertNotIn(forbidden, serialized_keys)


class RiskRoutePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_successful_persistence_is_called_and_does_not_change_risk_response(self):
        payload = {
            "live_rainfall_intensity_mm_per_hour": 0.0,
            "forecast_rainfall_intensity_mm_per_hour": 0.0,
            "river_level_m": 1.0,
            "river_change_m_per_hour": 0.0,
            "upstream_discharge_m3_per_s": 100.0,
            "station_id": "UPSTREAM-DEMO-01",
        }

        expected_request = RiskAssessmentRequest(**payload)
        expected_result = evaluate_risk(expected_request)

        with (
            patch("app.api.routes.risk.capture_previous_risk_level"),
            patch(
                "app.api.routes.risk.persist_risk_assessment",
                return_value=PersistenceResult(
                    attempted=True,
                    persisted=True,
                    status=STATUS_STORED,
                ),
            ) as mocked_persistence,
            patch("app.api.routes.risk.handle_risk_communication"),
            self.assertLogs("uvicorn.error", level="INFO") as captured_logs,
        ):
            response = self.client.post(
                "/api/risk/evaluate",
                json=payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            expected_result.model_dump(mode="json"),
        )
        mocked_persistence.assert_called_once()

        persisted_request, persisted_result = mocked_persistence.call_args.args
        self.assertEqual(persisted_request, expected_request)
        self.assertEqual(persisted_result, expected_result)

        logs = " ".join(captured_logs.output)
        self.assertIn("status=STORED", logs)
        self.assertIn("attempted=True", logs)
        self.assertIn("persisted=True", logs)

    def test_persistence_failure_does_not_change_risk_response(self):
        payload = {
            "live_rainfall_intensity_mm_per_hour": 35.0,
            "forecast_rainfall_intensity_mm_per_hour": 10.0,
            "river_level_m": 3.2,
            "river_change_m_per_hour": 0.20,
            "upstream_discharge_m3_per_s": 100.0,
            "station_id": "DEMO-01",
        }

        expected_request = RiskAssessmentRequest(**payload)
        expected_result = evaluate_risk(expected_request)

        with patch(
            "app.api.routes.risk.persist_risk_assessment",
            return_value=PersistenceResult(
                attempted=True,
                persisted=False,
                status=STATUS_WRITE_ERROR,
            ),
        ) as mocked_persistence:
            response = self.client.post(
                "/api/risk/evaluate",
                json=payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            expected_result.model_dump(mode="json"),
        )
        mocked_persistence.assert_called_once()

        persisted_request, persisted_result = mocked_persistence.call_args.args
        self.assertEqual(persisted_request, expected_request)
        self.assertEqual(persisted_result, expected_result)


if __name__ == "__main__":
    unittest.main()