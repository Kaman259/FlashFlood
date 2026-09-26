import logging
import os
from dataclasses import dataclass

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore as admin_firestore
from google.auth.credentials import AnonymousCredentials

from app.core.config import Settings, settings
from app.models.risk import RiskAssessmentRequest, RiskAssessmentResponse
from app.services.firebase_admin_service import get_real_firebase_app


logger = logging.getLogger(__name__)

RISK_ASSESSMENTS_COLLECTION = "risk_assessments"
FIRESTORE_EMULATOR_APP_NAME = "flashflood-firestore-emulator"

STATUS_DISABLED = "DISABLED"
STATUS_STORED = "STORED"
STATUS_CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
STATUS_INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
STATUS_WRITE_ERROR = "WRITE_ERROR"


@dataclass(frozen=True)
class PersistenceResult:
    attempted: bool
    persisted: bool
    status: str


class _EmulatorCredential(credentials.Base):
    """Firebase Admin credential wrapper for local Firestore emulator access."""

    def __init__(self) -> None:
        self._credential = AnonymousCredentials()

    def get_credential(self):
        return self._credential


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _validate_emulator_host(host: str) -> str:
    if "://" in host:
        raise ValueError(
            "FIRESTORE_EMULATOR_HOST must not include a URL scheme."
        )

    if any(character.isspace() for character in host):
        raise ValueError(
            "FIRESTORE_EMULATOR_HOST must not contain whitespace."
        )

    if ":" not in host:
        raise ValueError(
            "FIRESTORE_EMULATOR_HOST must use host:port format."
        )

    hostname, port_text = host.rsplit(":", 1)

    if not hostname or not port_text.isdigit():
        raise ValueError(
            "FIRESTORE_EMULATOR_HOST must use host:port format."
        )

    port = int(port_text)

    if port < 1 or port > 65535:
        raise ValueError(
            "FIRESTORE_EMULATOR_HOST contains an invalid port."
        )

    return host


def _validate_firestore_configuration(
    app_settings: Settings,
) -> tuple[str, str | None, str | None]:
    project_id = _normalized_optional(app_settings.firebase_project_id)
    emulator_host = _normalized_optional(app_settings.firestore_emulator_host)
    credential_path = _normalized_optional(
        app_settings.google_application_credentials
    )

    if not project_id:
        raise ValueError(
            "FIREBASE_PROJECT_ID is required when Firestore is enabled."
        )

    if emulator_host:
        emulator_host = _validate_emulator_host(emulator_host)

    return project_id, emulator_host, credential_path


def _get_or_initialize_emulator_app(
    project_id: str,
):
    try:
        app = firebase_admin.get_app(FIRESTORE_EMULATOR_APP_NAME)
    except ValueError:
        app = None

    if app is not None:
        if app.project_id != project_id:
            raise ValueError(
                "The initialized Firestore emulator app project does not match configuration."
            )

        return app

    return firebase_admin.initialize_app(
        credential=_EmulatorCredential(),
        options={"projectId": project_id},
        name=FIRESTORE_EMULATOR_APP_NAME,
    )


def _get_firestore_client(app_settings: Settings):
    project_id, emulator_host, _credential_path = (
        _validate_firestore_configuration(app_settings)
    )

    if emulator_host:
        os.environ["FIRESTORE_EMULATOR_HOST"] = emulator_host
        app = _get_or_initialize_emulator_app(project_id)
    else:
        os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
        app = get_real_firebase_app(app_settings)

    return admin_firestore.client(app=app)


def get_firestore_client(
    app_settings: Settings | None = None,
):
    """Return the configured Firestore client for narrow backend services."""

    return _get_firestore_client(app_settings or settings)


def _build_risk_assessment_document(
    request: RiskAssessmentRequest,
    result: RiskAssessmentResponse,
) -> dict:
    return {
        "created_at": admin_firestore.SERVER_TIMESTAMP,
        "risk_level": result.risk_level.value,
        "risk_score": result.risk_score,
        "reasons": list(result.reasons),
        "recommended_action": result.recommended_action,
        "warning_message": result.warning_message,
        "inputs": {
            "live_rainfall_intensity_mm_per_hour": (
                request.live_rainfall_intensity_mm_per_hour
            ),
            "forecast_rainfall_intensity_mm_per_hour": (
                request.forecast_rainfall_intensity_mm_per_hour
            ),
            "river_level_m": request.river_level_m,
            "river_change_m_per_hour": request.river_change_m_per_hour,
            "upstream_discharge_m3_per_s": request.upstream_discharge_m3_per_s,
            "station_id": request.station_id,
        },
    }


def persist_risk_assessment(
    request: RiskAssessmentRequest,
    result: RiskAssessmentResponse,
    app_settings: Settings | None = None,
) -> PersistenceResult:
    active_settings = app_settings or settings

    if not active_settings.firestore_enabled:
        return PersistenceResult(
            attempted=False,
            persisted=False,
            status=STATUS_DISABLED,
        )

    try:
        client = _get_firestore_client(active_settings)
    except Exception:
        logger.warning(
            "Firestore initialization unavailable; risk assessment persistence skipped."
        )
        return PersistenceResult(
            attempted=True,
            persisted=False,
            status=STATUS_INITIALIZATION_ERROR,
        )

    record = _build_risk_assessment_document(request, result)

    try:
        document = client.collection(RISK_ASSESSMENTS_COLLECTION).document()
        document.set(record)
    except Exception:
        logger.warning(
            "Firestore write unavailable; risk assessment persistence skipped."
        )
        return PersistenceResult(
            attempted=True,
            persisted=False,
            status=STATUS_WRITE_ERROR,
        )

    return PersistenceResult(
        attempted=True,
        persisted=True,
        status=STATUS_STORED,
    )