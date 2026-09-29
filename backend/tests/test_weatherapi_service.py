import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import httpx

from app.models.weather import (
    LocationWeatherData,
    WeatherDataStatus,
    WeatherFailureCode,
    WeatherLocationRole,
)
from app.services.rainfall_aggregation_service import aggregate_weather
from app.services.weather_service import WeatherLocationRequest
from app.services.weatherapi_service import (
    WEATHERAPI_FORECAST_URL,
    ResilientWeatherProvider,
    WeatherApiProvider,
)


def upstream_request():
    return WeatherLocationRequest(
        location_role=WeatherLocationRole.UPSTREAM,
        location_name="Mokokchung, Nagaland, India",
        latitude=26.31393,
        longitude=94.51675,
    )


def downstream_request():
    return WeatherLocationRequest(
        location_role=WeatherLocationRole.DOWNSTREAM,
        location_name="Sonari, Charaideo, Assam, India",
        latitude=27.0280,
        longitude=95.0312,
    )


def make_payload(
    *,
    latitude=26.32,
    longitude=94.52,
    current_precip_mm=1.5,
):
    observed_at = datetime(
        2026,
        9,
        25,
        6,
        15,
        tzinfo=timezone.utc,
    )
    first_hour = datetime(
        2026,
        9,
        25,
        5,
        30,
        tzinfo=timezone.utc,
    )

    values = [90.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]

    return {
        "location": {
            "lat": latitude,
            "lon": longitude,
        },
        "current": {
            "last_updated_epoch": int(observed_at.timestamp()),
            "precip_mm": current_precip_mm,
        },
        "forecast": {
            "forecastday": [
                {
                    "hour": [
                        {
                            "time_epoch": int(
                                (
                                    first_hour
                                    + timedelta(hours=index)
                                ).timestamp()
                            ),
                            "precip_mm": value,
                        }
                        for index, value in enumerate(values)
                    ]
                }
            ]
        },
    }


def response(payload, status_code=200):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", WEATHERAPI_FORECAST_URL),
    )


def available(
    role: WeatherLocationRole,
    *,
    source: str,
    live: float = 1.0,
    forecast: float = 2.0,
):
    req = upstream_request() if role == WeatherLocationRole.UPSTREAM else downstream_request()
    observed_at = datetime(2026, 9, 25, 6, 15, tzinfo=timezone.utc)
    start = datetime(2026, 9, 25, 6, 30, tzinfo=timezone.utc)

    return LocationWeatherData(
        location_role=role,
        location_name=req.location_name,
        requested_latitude=req.latitude,
        requested_longitude=req.longitude,
        provider_latitude=req.latitude,
        provider_longitude=req.longitude,
        source=source,
        status=WeatherDataStatus.AVAILABLE,
        observed_at=observed_at,
        live_rainfall_intensity_mm_per_hour=live,
        forecast_rainfall_intensity_mm_per_hour=forecast,
        forecast_horizon_hours=6,
        forecast_window_start=start,
        forecast_window_end=start + timedelta(hours=6),
        forecast_peak_time=start + timedelta(hours=5),
        rainfall_unit="mm/hour",
        current_interval_seconds=None if source == "WEATHERAPI" else 900,
    )


def unavailable(
    role: WeatherLocationRole,
    *,
    source: str,
    code: WeatherFailureCode,
):
    req = upstream_request() if role == WeatherLocationRole.UPSTREAM else downstream_request()

    return LocationWeatherData(
        location_role=role,
        location_name=req.location_name,
        requested_latitude=req.latitude,
        requested_longitude=req.longitude,
        source=source,
        status=WeatherDataStatus.UNAVAILABLE,
        failure_code=code,
        failure_message="Provider unavailable.",
    )


def pair_available(*, source: str, live=1.0, forecast=2.0):
    return (
        available(
            WeatherLocationRole.UPSTREAM,
            source=source,
            live=live,
            forecast=forecast,
        ),
        available(
            WeatherLocationRole.DOWNSTREAM,
            source=source,
            live=live,
            forecast=forecast,
        ),
    )


def pair_unavailable(*, source: str, code: WeatherFailureCode):
    return (
        unavailable(
            WeatherLocationRole.UPSTREAM,
            source=source,
            code=code,
        ),
        unavailable(
            WeatherLocationRole.DOWNSTREAM,
            source=source,
            code=code,
        ),
    )


class WeatherApiProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = WeatherApiProvider(
            forecast_horizon_hours=6,
            timeout_seconds=5,
            api_key="test-weather-key",
        )

    def fetch_one(
        self,
        *,
        location=None,
        payload=None,
        status_code=200,
    ):
        location = location or upstream_request()
        payload = make_payload() if payload is None else payload

        with patch(
            "app.services.weatherapi_service.httpx.get",
            return_value=response(payload, status_code),
        ) as mocked_get:
            result = self.provider.fetch_location(location)

        return result, mocked_get

    def test_successful_upstream_response(self):
        result, _ = self.fetch_one()

        self.assertEqual(result.status, WeatherDataStatus.AVAILABLE)
        self.assertEqual(result.location_role, WeatherLocationRole.UPSTREAM)
        self.assertEqual(result.source, "WEATHERAPI")

    def test_successful_downstream_response(self):
        result, _ = self.fetch_one(
            location=downstream_request(),
            payload=make_payload(
                latitude=27.03,
                longitude=95.03,
            ),
        )

        self.assertEqual(result.status, WeatherDataStatus.AVAILABLE)
        self.assertEqual(result.location_role, WeatherLocationRole.DOWNSTREAM)
        self.assertEqual(result.source, "WEATHERAPI")

    def test_request_url_key_coordinates_and_options(self):
        result, mocked_get = self.fetch_one(
            location=downstream_request(),
            payload=make_payload(
                latitude=27.03,
                longitude=95.03,
            ),
        )

        args, kwargs = mocked_get.call_args

        self.assertEqual(args[0], WEATHERAPI_FORECAST_URL)
        self.assertEqual(kwargs["params"]["key"], "test-weather-key")
        self.assertEqual(kwargs["params"]["q"], "27.028,95.0312")
        self.assertEqual(kwargs["params"]["days"], 2)
        self.assertEqual(kwargs["params"]["aqi"], "no")
        self.assertEqual(kwargs["params"]["alerts"], "no")
        self.assertEqual(kwargs["timeout"], 5)
        self.assertNotIn("test-weather-key", result.model_dump_json())

    def test_current_precipitation_normalization(self):
        result, _ = self.fetch_one(
            payload=make_payload(current_precip_mm=1.75),
        )

        self.assertEqual(
            result.live_rainfall_intensity_mm_per_hour,
            1.75,
        )
        self.assertIsNone(result.current_interval_seconds)

    def test_hourly_precipitation_normalization(self):
        result, _ = self.fetch_one()

        self.assertEqual(
            result.forecast_rainfall_intensity_mm_per_hour,
            6.0,
        )
        self.assertEqual(
            result.forecast_peak_time,
            datetime(2026, 9, 25, 11, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(
            result.forecast_window_start,
            datetime(2026, 9, 25, 6, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(
            result.forecast_window_end,
            datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc),
        )

    def test_zero_precipitation_remains_available_zero(self):
        payload = make_payload(current_precip_mm=0.0)

        for hour in payload["forecast"]["forecastday"][0]["hour"]:
            hour["precip_mm"] = 0.0

        result, _ = self.fetch_one(payload=payload)

        self.assertEqual(result.status, WeatherDataStatus.AVAILABLE)
        self.assertEqual(result.live_rainfall_intensity_mm_per_hour, 0.0)
        self.assertEqual(result.forecast_rainfall_intensity_mm_per_hour, 0.0)

    def test_missing_current_is_unavailable(self):
        payload = make_payload()
        del payload["current"]

        result, _ = self.fetch_one(payload=payload)

        self.assertEqual(result.failure_code, WeatherFailureCode.MISSING_FIELD)

    def test_missing_forecast_is_unavailable(self):
        payload = make_payload()
        del payload["forecast"]

        result, _ = self.fetch_one(payload=payload)

        self.assertEqual(result.failure_code, WeatherFailureCode.MISSING_FIELD)

    def test_missing_precip_mm_is_unavailable_not_zero(self):
        payload = make_payload()
        del payload["current"]["precip_mm"]

        result, _ = self.fetch_one(payload=payload)

        self.assertEqual(result.failure_code, WeatherFailureCode.MISSING_FIELD)
        self.assertIsNone(result.live_rainfall_intensity_mm_per_hour)

    def test_malformed_json_is_unavailable(self):
        bad_response = httpx.Response(
            200,
            content=b"not-json",
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", WEATHERAPI_FORECAST_URL),
        )

        with patch(
            "app.services.weatherapi_service.httpx.get",
            return_value=bad_response,
        ):
            result = self.provider.fetch_location(upstream_request())

        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.MALFORMED_RESPONSE,
        )

    def test_http_401_and_403_are_http_error(self):
        for status_code in (401, 403):
            with self.subTest(status_code=status_code):
                result, _ = self.fetch_one(
                    payload={"error": True},
                    status_code=status_code,
                )
                self.assertEqual(
                    result.failure_code,
                    WeatherFailureCode.HTTP_ERROR,
                )

    def test_http_429_is_http_error_without_retry(self):
        result, mocked_get = self.fetch_one(
            payload={"error": True},
            status_code=429,
        )

        mocked_get.assert_called_once()
        self.assertEqual(result.failure_code, WeatherFailureCode.HTTP_ERROR)
        self.assertEqual(
            result.failure_message,
            "WeatherAPI returned HTTP 429.",
        )

    def test_timeout(self):
        with patch(
            "app.services.weatherapi_service.httpx.get",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            result = self.provider.fetch_location(upstream_request())

        self.assertEqual(result.failure_code, WeatherFailureCode.TIMEOUT)

    def test_connection_failure(self):
        request = httpx.Request("GET", WEATHERAPI_FORECAST_URL)

        with patch(
            "app.services.weatherapi_service.httpx.get",
            side_effect=httpx.ConnectError(
                "connection failed",
                request=request,
            ),
        ):
            result = self.provider.fetch_location(upstream_request())

        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.CONNECTION_FAILURE,
        )

    def test_insufficient_future_forecast(self):
        payload = make_payload()
        payload["forecast"]["forecastday"][0]["hour"] = (
            payload["forecast"]["forecastday"][0]["hour"][:4]
        )

        result, _ = self.fetch_one(payload=payload)

        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.INSUFFICIENT_FORECAST_DATA,
        )

    def test_missing_api_key_is_invalid_configuration_without_network(self):
        provider = WeatherApiProvider(
            forecast_horizon_hours=6,
            timeout_seconds=5,
            api_key=None,
        )

        with patch(
            "app.services.weatherapi_service.httpx.get"
        ) as mocked_get:
            result = provider.fetch_location(upstream_request())

        mocked_get.assert_not_called()
        self.assertEqual(
            result.failure_code,
            WeatherFailureCode.INVALID_CONFIGURATION,
        )

    def test_two_location_behavior(self):
        downstream_payload = make_payload(
            latitude=27.03,
            longitude=95.03,
        )

        with patch(
            "app.services.weatherapi_service.httpx.get",
            side_effect=[
                response(make_payload()),
                response(downstream_payload),
            ],
        ) as mocked_get:
            upstream, downstream = self.provider.fetch_locations(
                upstream=upstream_request(),
                downstream=downstream_request(),
            )

        self.assertEqual(mocked_get.call_count, 2)
        self.assertEqual(upstream.source, "WEATHERAPI")
        self.assertEqual(downstream.source, "WEATHERAPI")


class ResilientWeatherProviderTests(unittest.TestCase):
    def make_provider(
        self,
        *,
        primary_result,
        fallback_result,
        fallback_enabled=True,
    ):
        primary = Mock()
        primary.fetch_locations.return_value = primary_result

        fallback = Mock()
        fallback.fetch_locations.return_value = fallback_result

        provider = ResilientWeatherProvider(
            primary_provider=primary,
            fallback_provider=fallback,
            fallback_enabled=fallback_enabled,
            cache_ttl_seconds=60,
        )

        return provider, primary, fallback

    def fetch(self, provider):
        return provider.fetch_locations(
            upstream=upstream_request(),
            downstream=downstream_request(),
        )

    def test_open_meteo_success_skips_fallback(self):
        provider, primary, fallback = self.make_provider(
            primary_result=pair_available(source="OPEN_METEO"),
            fallback_result=pair_available(source="WEATHERAPI"),
        )

        result = self.fetch(provider)

        primary.fetch_locations.assert_called_once()
        fallback.fetch_locations.assert_not_called()
        self.assertEqual(result[0].source, "OPEN_METEO")

    def test_open_meteo_failure_uses_fallback(self):
        provider, _, fallback = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.CONNECTION_FAILURE,
            ),
            fallback_result=pair_available(source="WEATHERAPI"),
        )

        self.fetch(provider)

        fallback.fetch_locations.assert_called_once()

    def test_open_meteo_429_uses_fallback(self):
        provider, _, fallback = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.HTTP_ERROR,
            ),
            fallback_result=pair_available(source="WEATHERAPI"),
        )

        self.fetch(provider)

        fallback.fetch_locations.assert_called_once()

    def test_open_meteo_timeout_uses_fallback(self):
        provider, _, fallback = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.TIMEOUT,
            ),
            fallback_result=pair_available(source="WEATHERAPI"),
        )

        self.fetch(provider)

        fallback.fetch_locations.assert_called_once()

    def test_open_meteo_malformed_uses_fallback(self):
        provider, _, fallback = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.MALFORMED_RESPONSE,
            ),
            fallback_result=pair_available(source="WEATHERAPI"),
        )

        self.fetch(provider)

        fallback.fetch_locations.assert_called_once()

    def test_fallback_success_produces_full_risk_ready_weather(self):
        provider, _, _ = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.HTTP_ERROR,
            ),
            fallback_result=pair_available(
                source="WEATHERAPI",
                live=3.0,
                forecast=4.0,
            ),
        )

        snapshot = aggregate_weather(*self.fetch(provider))

        self.assertEqual(snapshot.coverage_status.value, "FULL")
        self.assertTrue(snapshot.risk_input_ready)

    def test_both_providers_fail_remains_unavailable(self):
        provider, _, _ = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.HTTP_ERROR,
            ),
            fallback_result=pair_unavailable(
                source="WEATHERAPI",
                code=WeatherFailureCode.CONNECTION_FAILURE,
            ),
        )

        result = self.fetch(provider)
        snapshot = aggregate_weather(*result)

        self.assertEqual(snapshot.coverage_status.value, "UNAVAILABLE")
        self.assertFalse(snapshot.risk_input_ready)

        for location in result:
            self.assertIsNone(location.live_rainfall_intensity_mm_per_hour)
            self.assertIsNone(location.forecast_rainfall_intensity_mm_per_hour)

    def test_valid_zero_from_fallback_remains_zero(self):
        provider, _, _ = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.HTTP_ERROR,
            ),
            fallback_result=pair_available(
                source="WEATHERAPI",
                live=0.0,
                forecast=0.0,
            ),
        )

        snapshot = aggregate_weather(*self.fetch(provider))

        self.assertTrue(snapshot.risk_input_ready)
        self.assertEqual(
            snapshot.aggregated_live_rainfall_intensity_mm_per_hour,
            0.0,
        )
        self.assertEqual(
            snapshot.aggregated_forecast_rainfall_intensity_mm_per_hour,
            0.0,
        )

    def test_successful_fallback_is_cached_and_deep_copied(self):
        provider, primary, fallback = self.make_provider(
            primary_result=pair_unavailable(
                source="OPEN_METEO",
                code=WeatherFailureCode.HTTP_ERROR,
            ),
            fallback_result=pair_available(source="WEATHERAPI"),
        )

        with patch(
            "app.services.weatherapi_service.monotonic",
            side_effect=[100.0, 120.0],
        ):
            first = self.fetch(provider)
            second = self.fetch(provider)

        primary.fetch_locations.assert_called_once()
        fallback.fetch_locations.assert_called_once()
        self.assertEqual(first, second)
        self.assertIsNot(first[0], second[0])
        self.assertIsNot(first[1], second[1])

    def test_partial_primary_survives_worse_fallback(self):
        primary_result = (
            available(
                WeatherLocationRole.UPSTREAM,
                source="OPEN_METEO",
            ),
            unavailable(
                WeatherLocationRole.DOWNSTREAM,
                source="OPEN_METEO",
                code=WeatherFailureCode.HTTP_ERROR,
            ),
        )

        provider, _, _ = self.make_provider(
            primary_result=primary_result,
            fallback_result=pair_unavailable(
                source="WEATHERAPI",
                code=WeatherFailureCode.HTTP_ERROR,
            ),
        )

        snapshot = aggregate_weather(*self.fetch(provider))

        self.assertEqual(snapshot.coverage_status.value, "PARTIAL")
        self.assertFalse(snapshot.risk_input_ready)


if __name__ == "__main__":
    unittest.main()
