import logging
from dataclasses import dataclass

from firebase_admin import firestore as admin_firestore

from app.core.config import Settings, settings
from app.models.emergency import EmergencyReportRequest
from app.services.firestore_service import get_firestore_client


logger = logging.getLogger(__name__)

EMERGENCY_REPORTS_COLLECTION = "emergency_reports"
STATUS_RECEIVED = "received"
STATUS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EmergencyReportResult:
    status: str


def create_emergency_report(
    report: EmergencyReportRequest,
    app_settings: Settings | None = None,
) -> EmergencyReportResult:
    active_settings = app_settings or settings

    if (
        not active_settings.emergency_reporting_enabled
        or not active_settings.firestore_enabled
    ):
        return EmergencyReportResult(status=STATUS_UNAVAILABLE)

    record = {
        "created_at": admin_firestore.SERVER_TIMESTAMP,
        "category": report.category.value,
        "message": report.message,
        "status": "RECEIVED",
    }

    try:
        client = get_firestore_client(active_settings)
        client.collection(EMERGENCY_REPORTS_COLLECTION).document().set(record)
    except Exception:
        logger.warning("Emergency reporting storage unavailable.")
        return EmergencyReportResult(status=STATUS_UNAVAILABLE)

    return EmergencyReportResult(status=STATUS_RECEIVED)