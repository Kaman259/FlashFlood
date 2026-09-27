import logging
from dataclasses import dataclass

from firebase_admin import messaging

from app.core.config import Settings, settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.firebase_admin_service import get_real_firebase_app
from app.services.notification_registration_service import (
    disable_notification_installations,
    get_enabled_installation_ids,
)
# Backward-compatible imports for existing Stage 11 tests/callers. Ownership of
# transition policy now lives in risk_communication_service.
from app.services.risk_communication_service import (
    RiskTransitionContext,
    capture_previous_risk_level,
    is_risk_severity_increase,
)


logger = logging.getLogger(__name__)

FCM_MULTICAST_BATCH_SIZE = 500

STATUS_DISABLED = "DISABLED"
STATUS_NO_REGISTRATIONS = "NO_REGISTRATIONS"
STATUS_SENT = "SENT"
STATUS_PARTIAL_FAILURE = "PARTIAL_FAILURE"
STATUS_INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
STATUS_SEND_ERROR = "SEND_ERROR"

RISK_LABELS = {
    RiskLevel.GREEN: "GREEN - NORMAL",
    RiskLevel.YELLOW: "YELLOW - WATCH",
    RiskLevel.ORANGE: "ORANGE - WARNING",
    RiskLevel.RED: "RED - DANGER",
}


@dataclass(frozen=True)
class FcmSendResult:
    status: str
    attempted: bool = False
    sent_count: int = 0
    failed_count: int = 0


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
        return FcmSendResult(
            status=STATUS_DISABLED,
            attempted=False,
        )

    try:
        installation_ids = get_enabled_installation_ids(
            active_settings
        )
    except Exception:
        logger.warning("Notification registration lookup unavailable.")
        return FcmSendResult(
            status=STATUS_SEND_ERROR,
            attempted=True,
        )

    if not installation_ids:
        return FcmSendResult(
            status=STATUS_NO_REGISTRATIONS,
            attempted=True,
        )

    try:
        firebase_app = get_real_firebase_app(active_settings)
    except Exception:
        logger.warning(
            "FCM initialization unavailable; notification skipped."
        )
        return FcmSendResult(
            status=STATUS_INITIALIZATION_ERROR,
            attempted=True,
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

            for index, send_response in enumerate(response.responses):
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
        logger.warning("FCM send unavailable; notification skipped.")
        return FcmSendResult(
            status=STATUS_SEND_ERROR,
            attempted=True,
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
        attempted=True,
        sent_count=sent_count,
        failed_count=failed_count,
    )