from math import isclose

from app.models.risk import RiskAssessmentRequest
from app.models.telemetry import TelemetryRecord
from app.models.weather import (
    LocationWeatherData,
    WeatherCoverageStatus,
    WeatherDataStatus,
    WeatherLocationRole,
    WeatherSnapshot,
)
from app.services.telemetry_service import telemetry_to_risk_request


TIE_ABSOLUTE_TOLERANCE = 1e-9


def aggregate_weather(
    upstream: LocationWeatherData,
    downstream: LocationWeatherData,
) -> WeatherSnapshot:
    upstream_available = (
        upstream.status == WeatherDataStatus.AVAILABLE
    )
    downstream_available = (
        downstream.status == WeatherDataStatus.AVAILABLE
    )

    if upstream_available and downstream_available:
        return _build_full_snapshot(
            upstream=upstream,
            downstream=downstream,
        )

    if upstream_available or downstream_available:
        return WeatherSnapshot(
            upstream=upstream,
            downstream=downstream,
            coverage_status=WeatherCoverageStatus.PARTIAL,
            risk_input_ready=False,
        )

    return WeatherSnapshot(
        upstream=upstream,
        downstream=downstream,
        coverage_status=WeatherCoverageStatus.UNAVAILABLE,
        risk_input_ready=False,
    )


def weather_snapshot_to_risk_request(
    snapshot: WeatherSnapshot,
    telemetry: TelemetryRecord,
) -> RiskAssessmentRequest:
    if (
        snapshot.coverage_status
        != WeatherCoverageStatus.FULL
        or not snapshot.risk_input_ready
        or snapshot.aggregated_live_rainfall_intensity_mm_per_hour is None
        or snapshot.aggregated_forecast_rainfall_intensity_mm_per_hour is None
    ):
        raise ValueError(
            "A complete RiskAssessmentRequest requires FULL weather coverage."
        )

    return telemetry_to_risk_request(
        telemetry,
        live_rainfall_intensity_mm_per_hour=(
            snapshot.aggregated_live_rainfall_intensity_mm_per_hour
        ),
        forecast_rainfall_intensity_mm_per_hour=(
            snapshot.aggregated_forecast_rainfall_intensity_mm_per_hour
        ),
    )


def _build_full_snapshot(
    *,
    upstream: LocationWeatherData,
    downstream: LocationWeatherData,
) -> WeatherSnapshot:
    upstream_live = _required_available_value(
        upstream.live_rainfall_intensity_mm_per_hour,
        "upstream live rainfall",
    )
    downstream_live = _required_available_value(
        downstream.live_rainfall_intensity_mm_per_hour,
        "downstream live rainfall",
    )
    upstream_forecast = _required_available_value(
        upstream.forecast_rainfall_intensity_mm_per_hour,
        "upstream forecast rainfall",
    )
    downstream_forecast = _required_available_value(
        downstream.forecast_rainfall_intensity_mm_per_hour,
        "downstream forecast rainfall",
    )

    aggregated_live = max(
        upstream_live,
        downstream_live,
    )
    aggregated_forecast = max(
        upstream_forecast,
        downstream_forecast,
    )

    return WeatherSnapshot(
        upstream=upstream,
        downstream=downstream,
        coverage_status=WeatherCoverageStatus.FULL,
        aggregated_live_rainfall_intensity_mm_per_hour=aggregated_live,
        aggregated_forecast_rainfall_intensity_mm_per_hour=aggregated_forecast,
        live_driver_locations=_driver_locations(
            upstream_value=upstream_live,
            downstream_value=downstream_live,
            maximum_value=aggregated_live,
        ),
        forecast_driver_locations=_driver_locations(
            upstream_value=upstream_forecast,
            downstream_value=downstream_forecast,
            maximum_value=aggregated_forecast,
        ),
        risk_input_ready=True,
    )


def _driver_locations(
    *,
    upstream_value: float,
    downstream_value: float,
    maximum_value: float,
) -> list[WeatherLocationRole]:
    drivers: list[WeatherLocationRole] = []

    if isclose(
        upstream_value,
        maximum_value,
        rel_tol=0.0,
        abs_tol=TIE_ABSOLUTE_TOLERANCE,
    ):
        drivers.append(WeatherLocationRole.UPSTREAM)

    if isclose(
        downstream_value,
        maximum_value,
        rel_tol=0.0,
        abs_tol=TIE_ABSOLUTE_TOLERANCE,
    ):
        drivers.append(WeatherLocationRole.DOWNSTREAM)

    return drivers


def _required_available_value(
    value: float | None,
    label: str,
) -> float:
    if value is None:
        raise ValueError(
            f"AVAILABLE weather record is missing {label}."
        )
    return value