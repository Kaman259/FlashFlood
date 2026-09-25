from enum import IntEnum

from app.core.risk_thresholds import (
    PROTOTYPE_THRESHOLDS,
    RISK_LEVEL_MIN_SCORES,
    SeverityThresholds,
)
from app.models.risk import RiskAssessmentRequest, RiskAssessmentResponse, RiskLevel


class SignalSeverity(IntEnum):
    GREEN = 0
    YELLOW = 1
    ORANGE = 2
    RED = 3


RECOMMENDED_ACTIONS = {
    RiskLevel.GREEN: "Continue normal monitoring and follow official local updates.",
    RiskLevel.YELLOW: "Stay alert, monitor updates, and be ready to act if conditions worsen.",
    RiskLevel.ORANGE: "Prepare to move to a safer location and follow instructions from local authorities.",
    RiskLevel.RED: "Move to a safer location immediately if it is safe to do so and follow official emergency instructions.",
}


WARNING_MESSAGES = {
    RiskLevel.GREEN: "Green status: prototype indicators are within the normal monitoring range.",
    RiskLevel.YELLOW: "Yellow flood warning: one or more prototype indicators are elevated.",
    RiskLevel.ORANGE: "Orange flood warning: prototype indicators show elevated flood risk.",
    RiskLevel.RED: "Red flood warning: prototype indicators show critical conditions. Follow official emergency instructions.",
}


def classify_severity(
    value: float,
    thresholds: SeverityThresholds,
) -> SignalSeverity:
    if value >= thresholds.red:
        return SignalSeverity.RED

    if value >= thresholds.orange:
        return SignalSeverity.ORANGE

    if value >= thresholds.yellow:
        return SignalSeverity.YELLOW

    return SignalSeverity.GREEN


def calculate_risk_score(
    severities: list[SignalSeverity],
) -> int:
    dominant, support_1, support_2 = sorted(
        severities,
        reverse=True,
    )

    return (
        (25 * int(dominant))
        + (4 * int(support_1))
        + (4 * int(support_2))
    )


def risk_level_from_score(score: int) -> RiskLevel:
    if score >= RISK_LEVEL_MIN_SCORES["RED"]:
        return RiskLevel.RED

    if score >= RISK_LEVEL_MIN_SCORES["ORANGE"]:
        return RiskLevel.ORANGE

    if score >= RISK_LEVEL_MIN_SCORES["YELLOW"]:
        return RiskLevel.YELLOW

    return RiskLevel.GREEN


def _build_reasons(
    request: RiskAssessmentRequest,
    rainfall_severity: SignalSeverity,
    river_level_severity: SignalSeverity,
    river_change_severity: SignalSeverity,
) -> list[str]:
    reasons: list[str] = []

    if rainfall_severity > SignalSeverity.GREEN:
        reasons.append(
            f"Rainfall intensity is {rainfall_severity.name} under the prototype bands "
            f"({request.rainfall_intensity_mm_per_hour:.2f} mm/hour)."
        )

    if river_level_severity > SignalSeverity.GREEN:
        reasons.append(
            f"River level is {river_level_severity.name} for the demo station "
            f"({request.river_level_m:.2f} m)."
        )

    if river_change_severity > SignalSeverity.GREEN:
        reasons.append(
            f"River level rise rate is {river_change_severity.name} under the prototype bands "
            f"({request.river_change_m_per_hour:.2f} m/hour)."
        )

    if not reasons:
        if request.river_change_m_per_hour < 0:
            reasons.append(
                "All monitored indicators are below prototype warning thresholds, "
                "and the river level is falling."
            )
        else:
            reasons.append(
                "All monitored indicators are below prototype warning thresholds."
            )

    return reasons


def evaluate_risk(
    request: RiskAssessmentRequest,
) -> RiskAssessmentResponse:
    rainfall_severity = classify_severity(
        request.rainfall_intensity_mm_per_hour,
        PROTOTYPE_THRESHOLDS.rainfall_mm_per_hour,
    )

    river_level_severity = classify_severity(
        request.river_level_m,
        PROTOTYPE_THRESHOLDS.river_level_m,
    )

    river_change_severity = classify_severity(
        request.river_change_m_per_hour,
        PROTOTYPE_THRESHOLDS.river_rise_m_per_hour,
    )

    severities = [
        rainfall_severity,
        river_level_severity,
        river_change_severity,
    ]

    score = calculate_risk_score(severities)
    risk_level = risk_level_from_score(score)

    return RiskAssessmentResponse(
        risk_level=risk_level,
        risk_score=score,
        reasons=_build_reasons(
            request,
            rainfall_severity,
            river_level_severity,
            river_change_severity,
        ),
        recommended_action=RECOMMENDED_ACTIONS[risk_level],
        warning_message=WARNING_MESSAGES[risk_level],
    )
