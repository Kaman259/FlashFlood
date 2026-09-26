import logging
from dataclasses import dataclass

from firebase_admin import messaging
from google.cloud import firestore as google_firestore

from app.core.config import Settings, settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.firebase_admin_service import get_real_firebase_app
from app.services.firestore_service import (
    RISK_ASSESSMENTS_COLLECTION,
    get_firestore_client,
)
from app.services.notification_registration_service import (
    disable_notification_installations,
    get_enabled_installation_ids,
)


logger = logging.getLogger(__name__)

FCM_MULTICAST_BATCH_SIZE = 500

STATUS_DISABLED = "DISABLED"
STATUS_NO_REGISTRATIONS = "NO_REGISTRATIONS"
STATUS_SENT = "SENT"
STATUS_PARTIAL_FAILURE = "PARTIAL_FAILURE"
STATUS_INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
STATUS_SEND_ERROR = "SEND_ERROR"

RISK_SEVERITY = {
    RiskLevel.GREEN: 0,
    RiskLevel.YELLOW: 1,
    RiskLevel.ORANGE: 2,
    RiskLevel.RED: 3,
}

RISK_LABELS = {
    RiskLevel.GREEN: "GREEN - NORMAL",
    RiskLevel.YELLOW: "YELLOW - WATCH",
    RiskLevel.ORANGE: "ORANGE - WARNING",
    RiskLevel.RED: "RED - DANGER",
}


@dataclass(frozen=True)
class RiskTransitionContext:
    available: bool
    previous_level: RiskLevel | None


@dataclass(frozen=True)
class FcmSendResult:
    status: str
    sent_count: int = 0
    failed_count: int = 0


def capture_previous_risk_level(
    app_settings: Settings | None = None,
) -> RiskTransitionContext:
    active_settings = app_settings or settings

    if (
        not active_settings.fcm_enabled
        or not active_settings.firestore_enabled
    ):
        return RiskTransitionContext(
            available=False,
            previous_level=None,
        )

    try:
        client = get_firestore_client(active_settings)
        documents = list(
            client.collection(RISK_ASSESSMENTS_COLLECTION)
            .order_by(
                "created_at",
                direction=google_firestore.Query.DESCENDING,
            )
            .limit(1)
            .stream()
        )
    except Exception:
        logger.warning(
            "Previous risk state unavailable; notification transition check skipped."
        )
        return RiskTransitionContext(
            available=False,
            previous_level=None,
        )

    if not documents:
        return RiskTransitionContext(
            available=True,
            previous_level=None,
        )

    data = documents[0].to_dict() or {}
    value = data.get("risk_level")

    try:
        previous_level = RiskLevel(value)
    except (TypeError, ValueError):
        logger.warning(
            "Previous risk state is invalid; notification transition check skipped."
        )
        return RiskTransitionContext(
            available=False,
            previous_level=None,
        )

    return RiskTransitionContext(
        available=True,
        previous_level=previous_level,
    )


def is_risk_severity_increase(
    previous_level: RiskLevel | None,
    current_level: RiskLevel,
) -> bool:
    if previous_level is None:
        return False

    return (
        RISK_SEVERITY[current_level]
        > RISK_SEVERITY[previous_level]
    )


def build_risk_notification(
    result: RiskAssessmentResponse,
) -> messaging.Notification:
    return messaging.Notification(
        title="FlashFlood Alert",
        body=(
            f"Risk level increased to {RISK_LABELS[result.risk_level]}. "
            "Follow the current recommended safety guidance."
        ),
    )


def _chunks(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def send_risk_escalation_notification(
    result: RiskAssessmentResponse,
    app_settings: Settings | None = None,
) -> FcmSendResult:
    active_settings = app_settings or settings

    if not active_settings.fcm_enabled:
        return FcmSendResult(status=STATUS_DISABLED)

    try:
        installation_ids = get_enabled_installation_ids(
            active_settings
        )
    except Exception:
        logger.warning(
            "Notification registration lookup unavailable."
        )
        return FcmSendResult(
            status=STATUS_SEND_ERROR,
        )

    if not installation_ids:
        return FcmSendResult(
            status=STATUS_NO_REGISTRATIONS,
        )

    try:
        firebase_app = get_real_firebase_app(active_settings)
    except Exception:
        logger.warning(
            "FCM initialization unavailable; notification skipped."
        )
        return FcmSendResult(
            status=STATUS_INITIALIZATION_ERROR,
        )

    notification = build_risk_notification(result)
    sent_count = 0
    failed_count = 0
    unregistered_installation_ids: list[str] = []

    try:
        for batch in _chunks(
            installation_ids,
            FCM_MULTICAST_BATCH_SIZE,
        ):
            message = messaging.MulticastMessage(
                fids=batch,
                notification=notification,
            )
            response = messaging.send_each_for_multicast(
                message,
                app=firebase_app,
            )

            sent_count += response.success_count
            failed_count += response.failure_count

            for index, send_response in enumerate(
                response.responses
            ):
                if (
                    not send_response.success
                    and isinstance(
                        send_response.exception,
                        messaging.UnregisteredError,
                    )
                ):
                    unregistered_installation_ids.append(
                        batch[index]
                    )
    except Exception:
        logger.warning(
            "FCM send unavailable; notification skipped."
        )
        return FcmSendResult(
            status=STATUS_SEND_ERROR,
            sent_count=sent_count,
            failed_count=max(
                failed_count,
                len(installation_ids) - sent_count,
            ),
        )

    if unregistered_installation_ids:
        try:
            disable_notification_installations(
                unregistered_installation_ids,
                active_settings,
            )
        except Exception:
            logger.warning(
                "Could not disable unregistered notification installations."
            )

    status = (
        STATUS_SENT
        if failed_count == 0
        else STATUS_PARTIAL_FAILURE
    )

    return FcmSendResult(
        status=status,
        sent_count=sent_count,
        failed_count=failed_count,
    )