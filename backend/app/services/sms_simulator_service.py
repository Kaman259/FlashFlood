import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from firebase_admin import firestore as admin_firestore
from google.cloud import firestore as google_firestore

from app.core.config import Settings, settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.firestore_service import get_firestore_client


logger = logging.getLogger(__name__)

SMS_MESSAGES_COLLECTION = "sms_messages"
SIMULATED_RECIPIENT = "SIMULATED-RECIPIENT-001"
SIMULATED_DELIVERY_STATUS = "SIMULATED_DELIVERED"

TRIGGER_FCM_DISABLED = "FCM_DISABLED_FALLBACK"
TRIGGER_NO_FCM_REGISTRATIONS = "NO_FCM_REGISTRATIONS_FALLBACK"
TRIGGER_FCM_INITIALIZATION_FAILURE = "FCM_INITIALIZATION_FAILURE_FALLBACK"
TRIGGER_FCM_SEND_FAILURE = "FCM_SEND_FAILURE_FALLBACK"

STATUS_DISABLED = "DISABLED"
STATUS_SIMULATED = "SIMULATED"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_EMPTY = "EMPTY"


@dataclass(frozen=True)
class SmsSimulationResult:
    status: str


@dataclass(frozen=True)
class SmsLatestResult:
    status: str
    created_at: datetime | None = None
    risk_level: RiskLevel | None = None
    recipient_reference: str | None = None
    message_body: str | None = None
    delivery_status: str | None = None
    trigger_type: str | None = None


_LOCAL_RISK_SEVERITY = {
    RiskLevel.GREEN: 0,
    RiskLevel.YELLOW: 1,
    RiskLevel.ORANGE: 2,
    RiskLevel.RED: 3,
}
_local_sms_lock = Lock()
_local_previous_risk_level: RiskLevel | None = None
_local_latest_sms: SmsLatestResult | None = None


def reset_local_sms_demo_state() -> None:
    # Reset process-local SMS demo state. Intended for tests/demo restarts.
    global _local_previous_risk_level, _local_latest_sms

    with _local_sms_lock:
        _local_previous_risk_level = None
        _local_latest_sms = None


def build_red_fallback_message(result: RiskAssessmentResponse) -> str:
    return (
        "Risk level increased to RED - DANGER. "
        "Follow the current recommended safety guidance."
    )


def simulate_local_red_sms_transition(
    result: RiskAssessmentResponse,
    app_settings: Settings | None = None,
) -> SmsSimulationResult:
    # Record a free in-memory RED fallback for live portfolio demos only.
    active_settings = app_settings or settings

    if (
        not active_settings.sms_simulator_enabled
        or active_settings.firestore_enabled
        or active_settings.fcm_enabled
    ):
        return SmsSimulationResult(status=STATUS_DISABLED)

    global _local_previous_risk_level, _local_latest_sms

    with _local_sms_lock:
        previous_level = _local_previous_risk_level
        _local_previous_risk_level = result.risk_level

        if previous_level is None:
            return SmsSimulationResult(status=STATUS_DISABLED)

        severity_increased = (
            _LOCAL_RISK_SEVERITY[result.risk_level]
            > _LOCAL_RISK_SEVERITY[previous_level]
        )

        if not severity_increased or result.risk_level != RiskLevel.RED:
            return SmsSimulationResult(status=STATUS_DISABLED)

        _local_latest_sms = SmsLatestResult(
            status=STATUS_SIMULATED,
            created_at=datetime.now(timezone.utc),
            risk_level=result.risk_level,
            recipient_reference=SIMULATED_RECIPIENT,
            message_body=build_red_fallback_message(result),
            delivery_status=SIMULATED_DELIVERY_STATUS,
            trigger_type=TRIGGER_FCM_DISABLED,
        )

    return SmsSimulationResult(status=STATUS_SIMULATED)


def simulate_red_sms_fallback(
    result: RiskAssessmentResponse,
    trigger_type: str,
    app_settings: Settings | None = None,
) -> SmsSimulationResult:
    active_settings = app_settings or settings

    if (
        not active_settings.sms_simulator_enabled
        or not active_settings.firestore_enabled
    ):
        return SmsSimulationResult(status=STATUS_DISABLED)

    if result.risk_level != RiskLevel.RED:
        return SmsSimulationResult(status=STATUS_DISABLED)

    record = {
        "created_at": admin_firestore.SERVER_TIMESTAMP,
        "risk_level": result.risk_level.value,
        "recipient_reference": SIMULATED_RECIPIENT,
        "message_body": build_red_fallback_message(result),
        "delivery_status": SIMULATED_DELIVERY_STATUS,
        "trigger_type": trigger_type,
    }

    try:
        client = get_firestore_client(active_settings)
        client.collection(SMS_MESSAGES_COLLECTION).document().set(record)
    except Exception:
        logger.warning("SMS simulator persistence unavailable.")
        return SmsSimulationResult(status=STATUS_UNAVAILABLE)

    return SmsSimulationResult(status=STATUS_SIMULATED)


def get_latest_simulated_sms(
    app_settings: Settings | None = None,
) -> SmsLatestResult:
    active_settings = app_settings or settings

    if not active_settings.sms_simulator_enabled:
        return SmsLatestResult(status=STATUS_DISABLED)

    if not active_settings.firestore_enabled:
        if active_settings.fcm_enabled:
            return SmsLatestResult(status=STATUS_DISABLED)

        with _local_sms_lock:
            if _local_latest_sms is None:
                return SmsLatestResult(status=STATUS_EMPTY)

            return _local_latest_sms

    try:
        client = get_firestore_client(active_settings)
        documents = list(
            client.collection(SMS_MESSAGES_COLLECTION)
            .order_by(
                "created_at",
                direction=google_firestore.Query.DESCENDING,
            )
            .limit(1)
            .stream()
        )
    except Exception:
        logger.warning("SMS simulator history unavailable.")
        return SmsLatestResult(status=STATUS_UNAVAILABLE)

    if not documents:
        return SmsLatestResult(status=STATUS_EMPTY)

    data = documents[0].to_dict() or {}

    try:
        risk_level = RiskLevel(data.get("risk_level"))
    except (TypeError, ValueError):
        logger.warning("Latest SMS simulator record is invalid.")
        return SmsLatestResult(status=STATUS_UNAVAILABLE)

    return SmsLatestResult(
        status=STATUS_SIMULATED,
        created_at=data.get("created_at"),
        risk_level=risk_level,
        recipient_reference=data.get("recipient_reference"),
        message_body=data.get("message_body"),
        delivery_status=data.get("delivery_status"),
        trigger_type=data.get("trigger_type"),
    )