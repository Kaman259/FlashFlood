import unittest
from datetime import datetime, timezone

from app.models.risk import RiskLevel
from app.models.telemetry import TelemetryScenario
from app.models.weather import (
    LocationWeatherData,
    WeatherCoverageStatus,
    WeatherDataStatus,
    WeatherFailureCode,
    WeatherLocationRole,
)
from app.services.rainfall_aggregation_service import (
    aggregate_weather,
    weather_snapshot_to_risk_request,
)
from app.services.risk_service import evaluate_risk
from app.services.telemetry_service import SCENARIO_RECORDS


def available(
    role: WeatherLocationRole,
    live: float,
    forecast: float,
) -> LocationWeatherData:
    if role == WeatherLocationRole.UPSTREAM:
        name = "Mokokchung, Nagaland, India"
        latitude = 26.31393
        longitude = 94.51675
    else:
        name = "Sonari, Charaideo, Assam, India"
        latitude = 27.0280
        longitude = 95.0312

    return LocationWeatherData(
        location_role=role,
        location_name=name,
        requested_latitude=latitude,
        requested_longitude=longitude,
        provider_latitude=latitude,
        provider_longitude=longitude,
        status=WeatherDataStatus.AVAILABLE,
        observed_at=datetime(2026, 9, 25, 11, 45, tzinfo=timezone.utc),
        live_rainfall_intensity_mm_per_hour=live,
        forecast_rainfall_intensity_mm_per_hour=forecast,
        forecast_horizon_hours=6,
        forecast_window_start=datetime(
            2026, 9, 25, 12, 0, tzinfo=timezone.utc
        ),
        forecast_window_end=datetime(
            2026, 9, 25, 18, 0, tzinfo=timezone.utc
        ),
        forecast_peak_time=datetime(
            2026, 9, 25, 15, 0, tzinfo=timezone.utc
        ),
        rainfall_unit="mm/hour",
        current_interval_seconds=900,
    )


def unavailable(
    role: WeatherLocationRole,
) -> LocationWeatherData:
    if role == WeatherLocationRole.UPSTREAM:
        name = "Mokokchung, Nagaland, India"
        latitude = 26.31393
        longitude = 94.51675
    else:
        name = "Sonari, Charaideo, Assam, India"
        latitude = 27.0280
        longitude = 95.0312

    return LocationWeatherData(
        location_role=role,
        location_name=name,
        requested_latitude=latitude,
        requested_longitude=longitude,
        status=WeatherDataStatus.UNAVAILABLE,
        failure_code=WeatherFailureCode.TIMEOUT,
        failure_message="Timed out.",
    )


class RainfallAggregationTests(unittest.TestCase):
    def test_both_available_use_max_by_source(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=35.0,
                forecast=20.0,
            ),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=10.0,
                forecast=40.0,
            ),
        )

        self.assertEqual(
            snapshot.coverage_status,
            WeatherCoverageStatus.FULL,
        )
        self.assertTrue(snapshot.risk_input_ready)
        self.assertEqual(
            snapshot.aggregated_live_rainfall_intensity_mm_per_hour,
            35.0,
        )
        self.assertEqual(
            snapshot.aggregated_forecast_rainfall_intensity_mm_per_hour,
            40.0,
        )
        self.assertEqual(
            snapshot.live_driver_locations,
            [WeatherLocationRole.UPSTREAM],
        )
        self.assertEqual(
            snapshot.forecast_driver_locations,
            [WeatherLocationRole.DOWNSTREAM],
        )

    def test_live_and_forecast_ties_retain_both_drivers(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=20.0,
                forecast=40.0,
            ),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=20.0,
                forecast=40.0,
            ),
        )

        expected = [
            WeatherLocationRole.UPSTREAM,
            WeatherLocationRole.DOWNSTREAM,
        ]
        self.assertEqual(snapshot.live_driver_locations, expected)
        self.assertEqual(snapshot.forecast_driver_locations, expected)

    def test_upstream_unavailable_produces_partial(self):
        snapshot = aggregate_weather(
            upstream=unavailable(WeatherLocationRole.UPSTREAM),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=12.0,
                forecast=20.0,
            ),
        )

        self.assertEqual(
            snapshot.coverage_status,
            WeatherCoverageStatus.PARTIAL,
        )
        self.assertFalse(snapshot.risk_input_ready)
        self.assertIsNone(
            snapshot.aggregated_live_rainfall_intensity_mm_per_hour
        )
        self.assertIsNone(
            snapshot.aggregated_forecast_rainfall_intensity_mm_per_hour
        )

    def test_downstream_unavailable_produces_partial(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=12.0,
                forecast=20.0,
            ),
            downstream=unavailable(WeatherLocationRole.DOWNSTREAM),
        )

        self.assertEqual(
            snapshot.coverage_status,
            WeatherCoverageStatus.PARTIAL,
        )
        self.assertFalse(snapshot.risk_input_ready)

    def test_both_unavailable_produces_unavailable(self):
        snapshot = aggregate_weather(
            upstream=unavailable(WeatherLocationRole.UPSTREAM),
            downstream=unavailable(WeatherLocationRole.DOWNSTREAM),
        )

        self.assertEqual(
            snapshot.coverage_status,
            WeatherCoverageStatus.UNAVAILABLE,
        )
        self.assertFalse(snapshot.risk_input_ready)

    def test_zero_rainfall_is_distinct_from_unavailable(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=0.0,
                forecast=0.0,
            ),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=0.0,
                forecast=0.0,
            ),
        )

        self.assertEqual(
            snapshot.coverage_status,
            WeatherCoverageStatus.FULL,
        )
        self.assertTrue(snapshot.risk_input_ready)
        self.assertEqual(
            snapshot.aggregated_live_rainfall_intensity_mm_per_hour,
            0.0,
        )
        self.assertEqual(
            snapshot.aggregated_forecast_rainfall_intensity_mm_per_hour,
            0.0,
        )

    def test_aggregation_is_deterministic(self):
        upstream = available(
            WeatherLocationRole.UPSTREAM,
            live=35.0,
            forecast=40.0,
        )
        downstream = available(
            WeatherLocationRole.DOWNSTREAM,
            live=15.0,
            forecast=45.0,
        )

        first = aggregate_weather(upstream, downstream)

        for _ in range(10):
            self.assertEqual(
                aggregate_weather(upstream, downstream),
                first,
            )

    def test_partial_snapshot_cannot_build_risk_request(self):
        snapshot = aggregate_weather(
            upstream=unavailable(WeatherLocationRole.UPSTREAM),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=10.0,
                forecast=10.0,
            ),
        )

        with self.assertRaises(ValueError):
            weather_snapshot_to_risk_request(
                snapshot,
                SCENARIO_RECORDS[TelemetryScenario.NORMAL],
            )

    def test_upstream_live_55_drives_red_rainfall(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=55.0,
                forecast=10.0,
            ),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=0.0,
                forecast=10.0,
            ),
        )

        request = weather_snapshot_to_risk_request(
            snapshot,
            SCENARIO_RECORDS[TelemetryScenario.NORMAL],
        )
        result = evaluate_risk(request)

        self.assertEqual(
            request.live_rainfall_intensity_mm_per_hour,
            55.0,
        )
        self.assertEqual(result.risk_level, RiskLevel.RED)

    def test_forecast_40_and_45_drive_yellow_rainfall(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=0.0,
                forecast=40.0,
            ),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=0.0,
                forecast=45.0,
            ),
        )

        request = weather_snapshot_to_risk_request(
            snapshot,
            SCENARIO_RECORDS[TelemetryScenario.NORMAL],
        )
        result = evaluate_risk(request)

        self.assertEqual(
            request.forecast_rainfall_intensity_mm_per_hour,
            45.0,
        )
        self.assertEqual(result.risk_level, RiskLevel.YELLOW)

    def test_upstream_live_35_and_downstream_forecast_40_drive_orange(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=35.0,
                forecast=10.0,
            ),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=10.0,
                forecast=40.0,
            ),
        )

        request = weather_snapshot_to_risk_request(
            snapshot,
            SCENARIO_RECORDS[TelemetryScenario.NORMAL],
        )
        result = evaluate_risk(request)

        self.assertEqual(
            request.live_rainfall_intensity_mm_per_hour,
            35.0,
        )
        self.assertEqual(
            request.forecast_rainfall_intensity_mm_per_hour,
            40.0,
        )
        self.assertEqual(result.risk_level, RiskLevel.ORANGE)

    def test_all_four_risk_signals_still_score_99(self):
        snapshot = aggregate_weather(
            upstream=available(
                WeatherLocationRole.UPSTREAM,
                live=55.0,
                forecast=40.0,
            ),
            downstream=available(
                WeatherLocationRole.DOWNSTREAM,
                live=10.0,
                forecast=10.0,
            ),
        )

        request = weather_snapshot_to_risk_request(
            snapshot,
            SCENARIO_RECORDS[TelemetryScenario.CRITICAL_SURGE],
        )
        result = evaluate_risk(request)

        self.assertEqual(result.risk_level, RiskLevel.RED)
        self.assertEqual(result.risk_score, 99)


if __name__ == "__main__":
    unittest.main()