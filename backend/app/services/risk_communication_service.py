import logging
from dataclasses import dataclass

from google.cloud import firestore as google_firestore

from app.core.config import Settings, settings
from app.models.risk import RiskAssessmentResponse, RiskLevel
from app.services.firestore_service import (
    RISK_ASSESSMENTS_COLLECTION,
    PersistenceResult,
    get_firestore_client,
)


logger = logging.getLogger(__name__)

RISK_SEVERITY = {
    RiskLevel.GREEN: 0,
    RiskLevel.YELLOW: 1,
    RiskLevel.ORANGE: 2,
    RiskLevel.RED: 3,
}


@dataclass(frozen=True)
class RiskTransitionContext:
    available: bool
    previous_level: RiskLevel | None


def capture_previous_risk_level(
    app_settings: Settings | None = None,
) -> RiskTransitionContext:
    active_settings = app_settings or settings

    # Transition detection belongs to the shared communication layer, not FCM.
    # Firestore persistence is required so repeated polling can be deduplicated.
    if not active_settings.firestore_enabled:
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
            "Previous risk state unavailable; communication transition check skipped."
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

    try:
        previous_level = RiskLevel(data.get("risk_level"))
    except (TypeError, ValueError):
        logger.warning(
            "Previous risk state is invalid; communication transition check skipped."
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


def handle_risk_communication(
    result: RiskAssessmentResponse,
    transition: RiskTransitionContext,
    persistence: PersistenceResult,
    app_settings: Settings | None = None,
) -> None:
    active_settings = app_settings or settings

    # Free portfolio/demo mode: when Firebase persistence and FCM are both
    # intentionally disabled, keep a process-local live-risk transition
    # baseline for the SMS simulator. This does not affect the existing
    # Firestore/FCM communication policy below.
    if (
        active_settings.sms_simulator_enabled
        and not active_settings.firestore_enabled
        and not active_settings.fcm_enabled
    ):
        from app.services.sms_simulator_service import (
            simulate_local_red_sms_transition,
        )

        simulate_local_red_sms_transition(
            result,
            active_settings,
        )
        return

    if (
        not persistence.persisted
        or not transition.available
        or not is_risk_severity_increase(
            transition.previous_level,
            result.risk_level,
        )
    ):
        return

    # Local imports keep FCM specific code independent from transition policy.
    from app.services.fcm_service import (
        STATUS_DISABLED,
        STATUS_INITIALIZATION_ERROR,
        STATUS_NO_REGISTRATIONS,
        send_risk_escalation_notification,
    )
    from app.services.sms_simulator_service import (
        TRIGGER_FCM_DISABLED,
        TRIGGER_FCM_INITIALIZATION_FAILURE,
        TRIGGER_FCM_SEND_FAILURE,
        TRIGGER_NO_FCM_REGISTRATIONS,
        simulate_red_sms_fallback,
    )

    fcm_result = send_risk_escalation_notification(
        result,
        active_settings,
    )

    if result.risk_level != RiskLevel.RED:
        return

    # SMS is RED-only fallback. Any successful FCM destination suppresses SMS,
    # including partial-success multicast responses.
    if fcm_result.sent_count > 0:
        return

    if fcm_result.status == STATUS_DISABLED:
        trigger_type = TRIGGER_FCM_DISABLED
    elif fcm_result.status == STATUS_NO_REGISTRATIONS:
        trigger_type = TRIGGER_NO_FCM_REGISTRATIONS
    elif fcm_result.status == STATUS_INITIALIZATION_ERROR:
        trigger_type = TRIGGER_FCM_INITIALIZATION_FAILURE
    else:
        trigger_type = TRIGGER_FCM_SEND_FAILURE

    simulate_red_sms_fallback(
        result,
        trigger_type,
        active_settings,
    )