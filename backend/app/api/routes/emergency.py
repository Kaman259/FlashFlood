from collections import OrderedDict, deque
import threading
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.models.emergency import (
    EmergencyReportRequest,
    EmergencyReportResponse,
)
from app.services.emergency_report_service import (
    STATUS_RECEIVED,
    create_emergency_report,
)


router = APIRouter(
    prefix="/api/emergency",
    tags=["Emergency Reporting"],
)

REPORT_RATE_LIMIT = 5
REPORT_RATE_WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENTS = 1000


class _EmergencyReportRateLimiter:
    """Prototype-only bounded in-memory per-client limiter."""

    def __init__(self) -> None:
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, client_key: str) -> bool:
        now = time.monotonic()
        cutoff = now - REPORT_RATE_WINDOW_SECONDS

        with self._lock:
            events = self._events.get(client_key)

            if events is None:
                events = deque()
                self._events[client_key] = events

            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= REPORT_RATE_LIMIT:
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


_emergency_report_rate_limiter = _EmergencyReportRateLimiter()


@router.post(
    "/reports",
    response_model=EmergencyReportResponse,
    summary="Submit prototype emergency report",
)
def submit_emergency_report_endpoint(
    report: EmergencyReportRequest,
    request: Request,
) -> EmergencyReportResponse:
    if (
        not settings.emergency_reporting_enabled
        or not settings.firestore_enabled
    ):
        return EmergencyReportResponse(status="unavailable")

    client_key = (
        request.client.host
        if request.client is not None
        else "unknown-client"
    )

    if not _emergency_report_rate_limiter.allow(client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many emergency report requests.",
        )

    result = create_emergency_report(report)

    if result.status == STATUS_RECEIVED:
        return EmergencyReportResponse(status="received")

    return EmergencyReportResponse(status="unavailable")