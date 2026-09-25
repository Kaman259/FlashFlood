from dataclasses import dataclass


@dataclass(frozen=True)
class SeverityThresholds:
    yellow: float
    orange: float
    red: float


@dataclass(frozen=True)
class RainfallThresholds:
    forecast_yellow: float
    live_orange: float
    live_red: float


@dataclass(frozen=True)
class RiskThresholds:
    rainfall: RainfallThresholds
    river_level_m: SeverityThresholds
    river_rise_m_per_hour: SeverityThresholds
    upstream_discharge_m3_per_s: SeverityThresholds


# PROTOTYPE / DEMONSTRATION THRESHOLDS ONLY.
#
# These values are not scientifically validated universal flood-warning
# thresholds. River-level and discharge thresholds are demo-station values.
# Real deployment requires locally validated criteria for the specific
# monitoring station, river basin, and responsible authorities.
PROTOTYPE_THRESHOLDS = RiskThresholds(
    rainfall=RainfallThresholds(
        forecast_yellow=30.0,
        live_orange=30.0,
        live_red=50.0,
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
    upstream_discharge_m3_per_s=SeverityThresholds(
        yellow=200.0,
        orange=400.0,
        red=800.0,
    ),
)


RISK_LEVEL_MIN_SCORES = {
    "GREEN": 0,
    "YELLOW": 25,
    "ORANGE": 50,
    "RED": 75,
}
