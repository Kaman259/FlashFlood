import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.weather import (
    LocationWeatherData,
    WeatherDataStatus,
    WeatherFailureCode,
    WeatherLocationRole,
)


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


class WeatherEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.api.routes.weather.weather_provider.fetch_location")
    def test_full_weather_snapshot_returns_200(self, mocked_fetch):
        mocked_fetch.side_effect = [
            available(
                WeatherLocationRole.UPSTREAM,
                live=35.0,
                forecast=20.0,
            ),
            available(
                WeatherLocationRole.DOWNSTREAM,
                live=10.0,
                forecast=40.0,
            ),
        ]

        response = self.client.get("/api/weather")

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["coverage_status"], "FULL")
        self.assertTrue(body["risk_input_ready"])
        self.assertEqual(
            body["aggregated_live_rainfall_intensity_mm_per_hour"],
            35.0,
        )
        self.assertEqual(
            body["aggregated_forecast_rainfall_intensity_mm_per_hour"],
            40.0,
        )
        self.assertEqual(
            body["live_driver_locations"],
            ["UPSTREAM"],
        )
        self.assertEqual(
            body["forecast_driver_locations"],
            ["DOWNSTREAM"],
        )

    @patch("app.api.routes.weather.weather_provider.fetch_location")
    def test_partial_weather_snapshot_returns_200(self, mocked_fetch):
        mocked_fetch.side_effect = [
            unavailable(WeatherLocationRole.UPSTREAM),
            available(
                WeatherLocationRole.DOWNSTREAM,
                live=10.0,
                forecast=20.0,
            ),
        ]

        response = self.client.get("/api/weather")

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["coverage_status"], "PARTIAL")
        self.assertFalse(body["risk_input_ready"])
        self.assertIsNone(
            body["aggregated_live_rainfall_intensity_mm_per_hour"]
        )

    @patch("app.api.routes.weather.weather_provider.fetch_location")
    def test_unavailable_weather_snapshot_returns_503(self, mocked_fetch):
        mocked_fetch.side_effect = [
            unavailable(WeatherLocationRole.UPSTREAM),
            unavailable(WeatherLocationRole.DOWNSTREAM),
        ]

        response = self.client.get("/api/weather")

        self.assertEqual(response.status_code, 503)

        body = response.json()

        self.assertEqual(body["coverage_status"], "UNAVAILABLE")
        self.assertFalse(body["risk_input_ready"])
        self.assertEqual(
            body["upstream"]["failure_code"],
            "TIMEOUT",
        )
        self.assertEqual(
            body["downstream"]["failure_code"],
            "TIMEOUT",
        )


if __name__ == "__main__":
    unittest.main()