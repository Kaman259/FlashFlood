from collections import OrderedDict, deque
import threading
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.models.notifications import (
    NotificationRegistrationRequest,
    NotificationRegistrationResponse,
)
from app.services.notification_registration_service import (
    STATUS_DISABLED,
    STATUS_REGISTERED,
    register_notification_installation,
)


router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
)

REGISTRATION_RATE_LIMIT = 10
REGISTRATION_RATE_WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENTS = 1000


class _RegistrationRateLimiter:
    """Prototype-only bounded in-memory rate limiter.

    Production deployment should replace this with distributed abuse
    protection behind a trusted proxy or gateway.
    """

    def __init__(self) -> None:
        self._events: OrderedDict[str, deque[float]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()

    def allow(self, client_key: str) -> bool:
        now = time.monotonic()
        cutoff = now - REGISTRATION_RATE_WINDOW_SECONDS

        with self._lock:
            events = self._events.get(client_key)

            if events is None:
                events = deque()
                self._events[client_key] = events

            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= REGISTRATION_RATE_LIMIT:
                self._events.move_to_end(client_key)
                return False

            events.append(now)
            self._events.move_to_end(client_key)

            while len(self._events) > MAX_TRACKED_CLIENTS:
                self._events.popitem(last=False)

            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_registration_rate_limiter = _RegistrationRateLimiter()


@router.post(
    "/registration",
    response_model=NotificationRegistrationResponse,
    summary="Register browser installation for prototype alerts",
)
def register_notification_endpoint(
    registration: NotificationRegistrationRequest,
    request: Request,
) -> NotificationRegistrationResponse:
    if not settings.fcm_enabled or not settings.firestore_enabled:
        return NotificationRegistrationResponse(
            status="unavailable"
        )

    client_key = (
        request.client.host
        if request.client is not None
        else "unknown-client"
    )

    if not _registration_rate_limiter.allow(client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many notification registration requests.",
        )

    result = register_notification_installation(
        installation_id=registration.installation_id,
        enabled=registration.enabled,
    )

    if result.status == STATUS_REGISTERED:
        response_status = "registered"
    elif result.status == STATUS_DISABLED:
        response_status = "disabled"
    else:
        response_status = "unavailable"

    return NotificationRegistrationResponse(
        status=response_status
    )