import copy
import unittest
from unittest.mock import patch

import httpx

from app.models.weather import (
    WeatherDataStatus,
    WeatherFailureCode,
    WeatherLocationRole,
)
from app.services.weather_service import (
    OPEN_METEO_FORECAST_URL,
    OpenMeteoWeatherProvider,
)


def make_payload():
    return {
        "latitude": 26.32,
        "longitude": 94.52,
        "current_units": {
            "time": "iso8601",
            "interval": "seconds",
            "rain": "mm",
            "showers": "mm",
        },
        "current": {
            "time": "2026-09-25T11:45",
            "interval": 900,
            "rain": 1.0,
            "showers": 0.5,
        },
        "hourly_units": {
            "time": "iso8601",
            "rain": "mm",
            "showers": "mm",
        },
        "hourly": {
            "time": [
                "2026-09-25T11:00",
                "2026-09-25T12:00",
                "2026-09-25T13:00",
                "2026-09-25T14:00",
                "2026-09-25T15:00",
                "2026-09-25T16:00",
                "2026-09-25T17:00",
                "2026-09-25T18:00",
            ],
            "rain": [90.0, 80.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "showers": [0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
    }


def make_response(payload, status_code=200):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", OPEN_METEO_FORECAST_URL),
    )


class WeatherServiceTests(unittest.TestCase):
    def setUp(self):
        self.provider = OpenMeteoWeatherProvider(
            forecast_horizon_hours=6,
            timeout_seconds=5,
        )

    def fetch(self, payload=None):
        if payload is None:
            payload = make_payload()

        with patch(
            "app.services.weather_service.httpx.get",
            return_value=make_response(payload),
        ) as mocked_get:
            result = self.provider.fetch_location(
                location_role=WeatherLocationRole.UPSTREAM,
                location_name="Mokokchung, Nagaland, India",
                latitude=26.31393,
                longitude=94.51675,
            )

        return result, mocked_get

    def test_successful_upstream_response(self):
        result, mocked_get = self.fetch()

        self.assertEqual(result.status, WeatherDataStatus.AVAILABLE)
        self.assertEqual(result.location_role, WeatherLocationRole.UPSTREAM)
        self.assertEqual(result.provider_latitude, 26.32)
        self.assertEqual(result.provider_longitude, 94.52)

        _, kwargs = mocked_get.call_args
        self.assertEqual(kwargs["timeout"], 5)
        self.assertEqual(kwargs["params"]["latitude"], 26.31393)
        self.assertEqual(kwargs["params"]["longitude"], 94.51675)
        self.assertEqual(kwargs["params"]["current"], "rain,showers")
        self.assertEqual(kwargs["params"]["hourly"], "rain,showers")
        self.assertEqual(kwargs["params"]["precipitation_unit"], "mm")
        self.assertEqual(kwargs["params"]["timezone"], "GMT")
        self.assertEqual(kwargs["params"]["forecast_hours"], 8)

    def test_successful_downstream_response(self):
        payload = make_payload()
        payload["latitude"] = 27.03
        payload["longitude"] = 95.03

        with patch(
            "app.services.weather_service.httpx.get",
            return_value=make_response(payload),
        ) as mocked_get:
            result = self.provider.fetch_location(
                location_role=WeatherLocationRole.DOWNSTREAM,
                location_name="Sonari, Charaideo, Assam, India",
                latitude=27.0280,
                longitude=95.0312,
            )

        self.assertEqual(result.status, WeatherDataStatus.AVAILABLE)
        self.assertEqual(result.location_role, WeatherLocationRole.DOWNSTREAM)

        _, kwargs = mocked_get.call_args
        self.assertEqual(kwargs["params"]["latitude"], 27.0280)
        self.assertEqual(kwargs["params"]["longitude"], 95.0312)

    def test_current_rain_and_showers_are_converted_to_hourly_intensity(self):
        result, _ = self.fetch()

        # (1.0 + 0.5) mm over 900 seconds -> 6.0 mm/hour equivalent.
        self.assertEqual(
            result.live_rainfall_intensity_mm_per_hour,
            6.0,
        )
        self.assertEqual(result.current_interval_seconds, 900)
        self.assertEqual(result.rainfall_unit, "mm/hour")

    def test_zero_rainfall_remains_valid_zero(self):
        payload = make_payload()
        payload["current"]["rain"] = 0.0
        payload["current"]["showers"] = 0.0

        for index in range(len(payload["hourly"]["rain"])):
            payload["hourly"]["rain"][index] = 0.0
            payload["hourly"]["showers"][index] = 0.0

        result, _ = self.fetch(payload)

        self.assertEqual(result.status, WeatherDataStatus.AVAILABLE)
        self.assertEqual(result.live_rainfall_intensity_mm_per_hour, 0.0)
        self.assertEqual(result.forecast_rainfall_intensity_mm_per_hour, 0.0)

    def test_forecast_selects_six_complete_future_intervals(self):
        result, _ = self.fetch()

        self.assertEqual(
            result.forecast_window_start.isoformat(),
            "2026-09-25T12:00:00+00:00",
        )
        self.assertEqual(
            result.forecast_window_end.isoformat(),
            "2026-09-25T18:00:00+00:00",
        )
        self.assertEqual(
            result.forecast_rainfall_intensity_mm_per_hour,
            6.0,
        )
        self.assertEqual(
            result.forecast_peak_time.isoformat(),
            "2026-09-25T18:00:00+00:00",
        )

    def test_incomplete_current_hour_is_excluded(self):
        payload = make_payload()

        # These large values belong to endpoint timestamps 11:00 and 12:00.
        # 12:00 represents 11:00-12:00, which is incomplete at 11:45.
        payload["hourly"]["rain"][0] = 100.0
        payload["hourly"]["rain"][1] = 100.0

        result, _ = self.fetch(payload)

        self.assertEqual(
            result.forecast_rainfall_intensity_mm_per_hour,
            6.0,
        )

    def test_current_on_hour_boundary_selects_next_six_complete_hours(self):
        payload = make_payload()
        payload["current"]["time"] = "2026-09-25T11:00"

        result, _ = self.fetch(payload)

        # At exactly 11:00, the future complete intervals end 12:00..17:00.
        self.assertEqual(
            result.forecast_window_start.isoformat(),
            "2026-09-25T11:00:00+00:00",
        )
        self.assertEqual(
            result.forecast_window_end.isoformat(),
            "2026-09-25T17:00:00+00:00",
        )
        self.assertEqual(
            result.forecast_peak_time.isoformat(),
            "2026-09-25T12:00:00+00:00",
        )
        self.assertEqual(
            result.forecast_rainfall_intensity_mm_per_hour,
            80.0,
        )

    def test_earliest_forecast_peak_wins_tie(self):
        payload = make_payload()
        payload["hourly"]["rain"][4] = 7.0  # 15:00
        payload["hourly"]["rain"][5] = 7.0  # 16:00
        payload["hourly"]["rain"][6] = 2.0
        payload["hourly"]["rain"][7] = 1.0

        result, _ = self.fetch(payload)

        self.assertEqual(
            result.forecast_rainfall_intensity_mm_per_hour,
            7.0,
        )
        self.assertEqual(
            result.forecast_peak_time.isoformat(),
            "2026-09-25T15:00:00+00:00",
        )


    def test_hourly_showers_contribute_to_forecast_peak(self):
        payload = make_payload()

        for index in range(len(payload["hourly"]["rain"])):
            payload["hourly"]["rain"][index] = 0.0
            payload["hourly"]["showers"][index] = 0.0

        payload["hourly"]["showers"][5] = 12.5  # 16:00 endpoint.

        result, _ = self.fetch(payload)

        self.assertEqual(
            result.forecast_rainfall_intensity_mm_per_hour,
            12.5,
        )
        self.assertEqual(
            result.forecast_peak_time.isoformat(),
            "2026-09-25T16:00:00+00:00",
        )


    def test_normalization_is_deterministic(self):
        first, _ = self.fetch(make_payload())
        second, _ = self.fetch(make_payload())

        self.assertEqual(first, second)

    def test_normalized_source_and_units_are_explicit(self):
        result, _ = self.fetch()

        self.assertEqual(result.source, "OPEN_METEO")
        self.assertEqual(result.rainfall_unit, "mm/hour")
        self.assertEqual(result.forecast_horizon_hours, 6)

    def test_invalid_current_interval_is_unavailable(self):
        payload = make_payload()
        payload["current"]["interval"] = 0

        result, _ = self.fetch(payload)

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.MALFORMED_RESPONSE,
        )
        self.assertIsNone(result.live_rainfall_intensity_mm_per_hour)

    def test_insufficient_future_records_is_unavailable(self):
        payload = make_payload()
        for key in ("time", "rain", "showers"):
            payload["hourly"][key] = payload["hourly"][key][:-1]

        result, _ = self.fetch(payload)

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.INSUFFICIENT_FORECAST_DATA,
        )

    def test_malformed_timestamp_is_unavailable(self):
        payload = make_payload()
        payload["hourly"]["time"][3] = "not-a-time"

        result, _ = self.fetch(payload)

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.MALFORMED_RESPONSE,
        )

    def test_mismatched_hourly_arrays_are_unavailable(self):
        payload = make_payload()
        payload["hourly"]["showers"].pop()

        result, _ = self.fetch(payload)

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.MALFORMED_RESPONSE,
        )

    def test_missing_fields_are_unavailable(self):
        cases = [
            ("current",),
            ("current_units",),
            ("hourly",),
            ("hourly_units",),
            ("current", "rain"),
            ("current", "showers"),
            ("current", "interval"),
            ("current_units", "rain"),
            ("current_units", "showers"),
            ("current_units", "interval"),
            ("hourly", "rain"),
            ("hourly", "showers"),
            ("hourly_units", "rain"),
            ("hourly_units", "showers"),
        ]

        for path in cases:
            with self.subTest(path=path):
                payload = copy.deepcopy(make_payload())
                target = payload
                for key in path[:-1]:
                    target = target[key]
                del target[path[-1]]

                result, _ = self.fetch(payload)

                self.assertEqual(
                    result.status,
                    WeatherDataStatus.UNAVAILABLE,
                )
                self.assertEqual(
                    result.failure_code,
                    WeatherFailureCode.MISSING_FIELD,
                )

    def test_invalid_units_are_unavailable(self):
        payload = make_payload()
        payload["current_units"]["rain"] = "inch"

        result, _ = self.fetch(payload)

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.INVALID_UNIT,
        )

    def test_http_failure_is_unavailable(self):
        response = httpx.Response(
            500,
            json={"error": True},
            request=httpx.Request("GET", OPEN_METEO_FORECAST_URL),
        )

        with patch(
            "app.services.weather_service.httpx.get",
            return_value=response,
        ):
            result = self.provider.fetch_location(
                location_role=WeatherLocationRole.UPSTREAM,
                location_name="Mokokchung, Nagaland, India",
                latitude=26.31393,
                longitude=94.51675,
            )

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.HTTP_ERROR,
        )

    def test_timeout_is_unavailable(self):
        with patch(
            "app.services.weather_service.httpx.get",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            result = self.provider.fetch_location(
                location_role=WeatherLocationRole.UPSTREAM,
                location_name="Mokokchung, Nagaland, India",
                latitude=26.31393,
                longitude=94.51675,
            )

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.TIMEOUT,
        )

    def test_connection_failure_is_unavailable(self):
        request = httpx.Request("GET", OPEN_METEO_FORECAST_URL)

        with patch(
            "app.services.weather_service.httpx.get",
            side_effect=httpx.ConnectError(
                "connection failed",
                request=request,
            ),
        ):
            result = self.provider.fetch_location(
                location_role=WeatherLocationRole.UPSTREAM,
                location_name="Mokokchung, Nagaland, India",
                latitude=26.31393,
                longitude=94.51675,
            )

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.CONNECTION_FAILURE,
        )

    def test_malformed_json_is_unavailable(self):
        response = httpx.Response(
            200,
            content=b"not-json",
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", OPEN_METEO_FORECAST_URL),
        )

        with patch(
            "app.services.weather_service.httpx.get",
            return_value=response,
        ):
            result = self.provider.fetch_location(
                location_role=WeatherLocationRole.UPSTREAM,
                location_name="Mokokchung, Nagaland, India",
                latitude=26.31393,
                longitude=94.51675,
            )

        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.MALFORMED_RESPONSE,
        )

    def test_invalid_provider_configuration_does_not_call_network(self):
        provider = OpenMeteoWeatherProvider(
            forecast_horizon_hours=0,
            timeout_seconds=5,
        )

        with patch(
            "app.services.weather_service.httpx.get"
        ) as mocked_get:
            result = provider.fetch_location(
                location_role=WeatherLocationRole.UPSTREAM,
                location_name="Mokokchung, Nagaland, India",
                latitude=26.31393,
                longitude=94.51675,
            )

        mocked_get.assert_not_called()
        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.INVALID_CONFIGURATION,
        )



    def test_invalid_location_is_structured_unavailable(self):
        with patch(
            "app.services.weather_service.httpx.get"
        ) as mocked_get:
            result = self.provider.fetch_location(
                location_role=WeatherLocationRole.UPSTREAM,
                location_name="Invalid location",
                latitude=91.0,
                longitude=94.51675,
            )

        mocked_get.assert_not_called()
        self.assertEqual(result.status, WeatherDataStatus.UNAVAILABLE)
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.INVALID_CONFIGURATION,
        )

    def test_settings_reject_invalid_coordinates_and_limits(self):
        from pydantic import ValidationError

        from app.core.config import Settings

        invalid_cases = [
            {"weather_upstream_latitude": 91},
            {"weather_upstream_longitude": 181},
            {"weather_downstream_latitude": -91},
            {"weather_downstream_longitude": -181},
            {"weather_forecast_horizon_hours": 0},
            {"weather_timeout_seconds": 0},
        ]

        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError):
                    Settings(_env_file=None, **overrides)


if __name__ == "__main__":
    unittest.main()