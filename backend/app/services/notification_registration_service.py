import hashlib
import logging
from dataclasses import dataclass

from firebase_admin import firestore as admin_firestore

from app.core.config import Settings, settings
from app.services.firestore_service import get_firestore_client


logger = logging.getLogger(__name__)

NOTIFICATION_REGISTRATIONS_COLLECTION = "notification_registrations"

STATUS_REGISTERED = "registered"
STATUS_DISABLED = "disabled"
STATUS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class NotificationRegistrationResult:
    status: str


def _document_id_for_installation(installation_id: str) -> str:
    return hashlib.sha256(
        installation_id.encode("utf-8")
    ).hexdigest()


def register_notification_installation(
    installation_id: str,
    enabled: bool,
    app_settings: Settings | None = None,
) -> NotificationRegistrationResult:
    active_settings = app_settings or settings

    if (
        not active_settings.fcm_enabled
        or not active_settings.firestore_enabled
    ):
        return NotificationRegistrationResult(
            status=STATUS_UNAVAILABLE,
        )

    try:
        client = get_firestore_client(active_settings)
        document = client.collection(
            NOTIFICATION_REGISTRATIONS_COLLECTION
        ).document(
            _document_id_for_installation(installation_id)
        )
        snapshot = document.get()
    except Exception:
        logger.warning(
            "Notification registration storage unavailable."
        )
        return NotificationRegistrationResult(
            status=STATUS_UNAVAILABLE,
        )

    if not enabled:
        if getattr(snapshot, "exists", False):
            try:
                document.set(
                    {
                        "enabled": False,
                        "updated_at": admin_firestore.SERVER_TIMESTAMP,
                    },
                    merge=True,
                )
            except Exception:
                logger.warning(
                    "Notification registration update unavailable."
                )
                return NotificationRegistrationResult(
                    status=STATUS_UNAVAILABLE,
                )

        return NotificationRegistrationResult(
            status=STATUS_DISABLED,
        )

    record = {
        "installation_id": installation_id,
        "enabled": True,
        "updated_at": admin_firestore.SERVER_TIMESTAMP,
    }

    if not getattr(snapshot, "exists", False):
        record["created_at"] = admin_firestore.SERVER_TIMESTAMP

    try:
        document.set(record, merge=True)
    except Exception:
        logger.warning(
            "Notification registration write unavailable."
        )
        return NotificationRegistrationResult(
            status=STATUS_UNAVAILABLE,
        )

    return NotificationRegistrationResult(
        status=STATUS_REGISTERED,
    )


def get_enabled_installation_ids(
    app_settings: Settings | None = None,
) -> list[str]:
    active_settings = app_settings or settings

    if (
        not active_settings.fcm_enabled
        or not active_settings.firestore_enabled
    ):
        return []

    client = get_firestore_client(active_settings)

    documents = (
        client.collection(NOTIFICATION_REGISTRATIONS_COLLECTION)
        .where("enabled", "==", True)
        .stream()
    )

    installation_ids: list[str] = []

    for document in documents:
        data = document.to_dict() or {}
        installation_id = data.get("installation_id")

        if isinstance(installation_id, str) and installation_id:
            installation_ids.append(installation_id)

    return installation_ids


def disable_notification_installations(
    installation_ids: list[str],
    app_settings: Settings | None = None,
) -> None:
    active_settings = app_settings or settings

    if (
        not installation_ids
        or not active_settings.firestore_enabled
    ):
        return

    client = get_firestore_client(active_settings)
    collection = client.collection(
        NOTIFICATION_REGISTRATIONS_COLLECTION
    )

    for installation_id in installation_ids:
        document = collection.document(
            _document_id_for_installation(installation_id)
        )
        document.set(
            {
                "enabled": False,
                "updated_at": admin_firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )