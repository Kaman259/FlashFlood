from dataclasses import dataclass


@dataclass(frozen=True)
class SeverityThresholds:
    yellow: float
    orange: float
    red: float


@dataclass(frozen=True)
class RiskThresholds:
    rainfall_mm_per_hour: SeverityThresholds
    river_level_m: SeverityThresholds
    river_rise_m_per_hour: SeverityThresholds


# PROTOTYPE / DEMONSTRATION THRESHOLDS ONLY.
# These are not scientifically validated universal flood thresholds.
# Real deployment requires locally validated rainfall thresholds and
# river thresholds calibrated for the specific station and river basin.
PROTOTYPE_THRESHOLDS = RiskThresholds(
    rainfall_mm_per_hour=SeverityThresholds(
        yellow=15.0,
        orange=30.0,
        red=50.0,
    ),
    river_level_m=SeverityThresholds(
        yellow=2.0,
        orange=3.0,
        red=4.0,
    ),
    river_rise_m_per_hour=SeverityThresholds(
        yellow=0.10,
        orange=0.30,
        red=0.60,
    ),
)


RISK_LEVEL_MIN_SCORES = {
    "GREEN": 0,
    "YELLOW": 25,
    "ORANGE": 50,
    "RED": 75,
}
