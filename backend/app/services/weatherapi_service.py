from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from threading import Lock
from time import monotonic
from typing import Any, Protocol

import httpx

from app.models.weather import (
    LocationWeatherData,
    WeatherDataStatus,
    WeatherFailureCode,
)
from app.services.weather_service import WeatherLocationRequest


WEATHERAPI_FORECAST_URL = "https://api.weatherapi.com/v1/forecast.json"


class WeatherPairProvider(Protocol):
    def fetch_locations(
        self,
        *,
        upstream: WeatherLocationRequest,
        downstream: WeatherLocationRequest,
    ) -> tuple[LocationWeatherData, LocationWeatherData]:
        ...


class WeatherApiProvider:
    """Normalize WeatherAPI forecast responses into FlashFlood weather models."""

    def __init__(
        self,
        *,
        forecast_horizon_hours: int,
        timeout_seconds: float,
        api_key: str | None,
    ) -> None:
        self.forecast_horizon_hours = forecast_horizon_hours
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key.strip() if api_key else None

    def fetch_locations(
        self,
        *,
        upstream: WeatherLocationRequest,
        downstream: WeatherLocationRequest,
    ) -> tuple[LocationWeatherData, LocationWeatherData]:
        return (
            self.fetch_location(upstream),
            self.fetch_location(downstream),
        )

    def fetch_location(
        self,
        location: WeatherLocationRequest,
    ) -> LocationWeatherData:
        configuration_error = self._validate_configuration(location)
        if configuration_error is not None:
            return self._unavailable(
                location=location,
                failure_code=WeatherFailureCode.INVALID_CONFIGURATION,
                failure_message=configuration_error,
            )

        params = {
            "key": self.api_key,
            "q": f"{location.latitude},{location.longitude}",
            "days": 2,
            "aqi": "no",
            "alerts": "no",
        }

        try:
            response = httpx.get(
                WEATHERAPI_FORECAST_URL,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            return self._unavailable(
                location=location,
                failure_code=WeatherFailureCode.TIMEOUT,
                failure_message="WeatherAPI request timed out.",
            )
        except httpx.ConnectError:
            return self._unavailable(
                location=location,
                failure_code=WeatherFailureCode.CONNECTION_FAILURE,
                failure_message="Could not connect to WeatherAPI.",
            )
        except httpx.HTTPStatusError as exc:
            return self._unavailable(
                location=location,
                failure_code=WeatherFailureCode.HTTP_ERROR,
                failure_message=(
                    f"WeatherAPI returned HTTP {exc.response.status_code}."
                ),
            )
        except httpx.RequestError:
            return self._unavailable(
                location=location,
                failure_code=WeatherFailureCode.CONNECTION_FAILURE,
                failure_message="WeatherAPI request failed.",
            )

        try:
            payload = response.json()
        except ValueError:
            return self._unavailable(
                location=location,
                failure_code=WeatherFailureCode.MALFORMED_RESPONSE,
                failure_message="WeatherAPI returned malformed JSON.",
            )

        try:
            return self._normalize_payload(
                payload=payload,
                location=location,
            )
        except WeatherApiNormalizationError as exc:
            return self._unavailable(
                location=location,
                failure_code=exc.code,
                failure_message=exc.message,
            )

    def _validate_configuration(
        self,
        location: WeatherLocationRequest,
    ) -> str | None:
        if not self.api_key:
            return (
                "WeatherAPI fallback is enabled but no API key is configured."
            )
        if not -90 <= location.latitude <= 90:
            return "Latitude must be between -90 and 90."
        if not -180 <= location.longitude <= 180:
            return "Longitude must be between -180 and 180."
        if self.forecast_horizon_hours <= 0:
            return "Forecast horizon must be greater than zero."
        if self.timeout_seconds <= 0:
            return "Weather timeout must be greater than zero."
        return None

    def _normalize_payload(
        self,
        *,
        payload: Any,
        location: WeatherLocationRequest,
    ) -> LocationWeatherData:
        if not isinstance(payload, dict):
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "WeatherAPI response must be a JSON object.",
            )

        provider_location = self._required_dict(payload, "location")
        current = self._required_dict(payload, "current")
        forecast = self._required_dict(payload, "forecast")

        provider_latitude = self._required_number(
            provider_location,
            "lat",
            "location.lat",
        )
        provider_longitude = self._required_number(
            provider_location,
            "lon",
            "location.lon",
        )

        if not -90 <= provider_latitude <= 90:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "WeatherAPI provider latitude is outside the valid range.",
            )
        if not -180 <= provider_longitude <= 180:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "WeatherAPI provider longitude is outside the valid range.",
            )

        observed_at = self._required_epoch(
            current,
            "last_updated_epoch",
            "current.last_updated_epoch",
        )
        live_intensity = self._required_non_negative_number(
            current,
            "precip_mm",
            "current.precip_mm",
        )

        forecast_days = self._required_list(
            forecast,
            "forecastday",
            "forecast.forecastday",
        )

        hourly_values: dict[datetime, float] = {}

        for day_index, day in enumerate(forecast_days):
            if not isinstance(day, dict):
                raise WeatherApiNormalizationError(
                    WeatherFailureCode.MALFORMED_RESPONSE,
                    (
                        "WeatherAPI field "
                        f"forecast.forecastday[{day_index}] must be an object."
                    ),
                )

            hours = self._required_list(
                day,
                "hour",
                f"forecast.forecastday[{day_index}].hour",
            )

            for hour_index, hour in enumerate(hours):
                if not isinstance(hour, dict):
                    raise WeatherApiNormalizationError(
                        WeatherFailureCode.MALFORMED_RESPONSE,
                        (
                            "WeatherAPI hourly forecast entry "
                            f"{day_index}:{hour_index} must be an object."
                        ),
                    )

                timestamp = self._required_epoch(
                    hour,
                    "time_epoch",
                    (
                        "forecast.forecastday"
                        f"[{day_index}].hour[{hour_index}].time_epoch"
                    ),
                )
                precipitation = self._required_non_negative_number(
                    hour,
                    "precip_mm",
                    (
                        "forecast.forecastday"
                        f"[{day_index}].hour[{hour_index}].precip_mm"
                    ),
                )

                if timestamp in hourly_values:
                    raise WeatherApiNormalizationError(
                        WeatherFailureCode.MALFORMED_RESPONSE,
                        (
                            "WeatherAPI forecast contains duplicate "
                            "hourly timestamps."
                        ),
                    )

                hourly_values[timestamp] = precipitation

        ordered_times = sorted(hourly_values)
        first_forecast_hour = next(
            (
                timestamp
                for timestamp in ordered_times
                if timestamp >= observed_at
            ),
            None,
        )

        if first_forecast_hour is None:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.INSUFFICIENT_FORECAST_DATA,
                "WeatherAPI did not provide a future hourly forecast.",
            )

        expected_hours = [
            first_forecast_hour + timedelta(hours=offset)
            for offset in range(self.forecast_horizon_hours)
        ]

        if any(
            timestamp not in hourly_values
            for timestamp in expected_hours
        ):
            raise WeatherApiNormalizationError(
                WeatherFailureCode.INSUFFICIENT_FORECAST_DATA,
                (
                    "WeatherAPI did not provide all complete future hourly "
                    "intervals required by the configured forecast horizon."
                ),
            )

        selected_values = [
            (timestamp, hourly_values[timestamp])
            for timestamp in expected_hours
        ]

        peak_time, peak_value = selected_values[0]
        for timestamp, value in selected_values[1:]:
            if value > peak_value:
                peak_time = timestamp
                peak_value = value

        return LocationWeatherData(
            location_role=location.location_role,
            location_name=location.location_name,
            requested_latitude=location.latitude,
            requested_longitude=location.longitude,
            provider_latitude=provider_latitude,
            provider_longitude=provider_longitude,
            source="WEATHERAPI",
            status=WeatherDataStatus.AVAILABLE,
            observed_at=observed_at,
            live_rainfall_intensity_mm_per_hour=live_intensity,
            forecast_rainfall_intensity_mm_per_hour=peak_value,
            forecast_horizon_hours=self.forecast_horizon_hours,
            forecast_window_start=first_forecast_hour,
            forecast_window_end=(
                first_forecast_hour
                + timedelta(hours=self.forecast_horizon_hours)
            ),
            forecast_peak_time=peak_time,
            rainfall_unit="mm/hour",
            current_interval_seconds=None,
        )

    def _required_dict(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> dict[str, Any]:
        if field_name not in payload:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MISSING_FIELD,
                f"Missing WeatherAPI field: {field_name}.",
            )
        value = payload[field_name]
        if not isinstance(value, dict):
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"WeatherAPI field {field_name} must be an object.",
            )
        return value

    def _required_list(
        self,
        payload: dict[str, Any],
        field_name: str,
        field_path: str,
    ) -> list[Any]:
        if field_name not in payload:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MISSING_FIELD,
                f"Missing WeatherAPI field: {field_path}.",
            )
        value = payload[field_name]
        if not isinstance(value, list):
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"WeatherAPI field {field_path} must be a list.",
            )
        return value

    def _required_number(
        self,
        payload: dict[str, Any],
        field_name: str,
        field_path: str,
    ) -> float:
        if field_name not in payload:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MISSING_FIELD,
                f"Missing WeatherAPI field: {field_path}.",
            )
        value = payload[field_name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
        ):
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"WeatherAPI field {field_path} must be numeric.",
            )
        return float(value)

    def _required_non_negative_number(
        self,
        payload: dict[str, Any],
        field_name: str,
        field_path: str,
    ) -> float:
        value = self._required_number(
            payload,
            field_name,
            field_path,
        )
        if value < 0:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"WeatherAPI field {field_path} cannot be negative.",
            )
        return value

    def _required_epoch(
        self,
        payload: dict[str, Any],
        field_name: str,
        field_path: str,
    ) -> datetime:
        epoch = self._required_number(
            payload,
            field_name,
            field_path,
        )
        if epoch < 0:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"WeatherAPI field {field_path} cannot be negative.",
            )

        try:
            return datetime.fromtimestamp(
                epoch,
                tz=timezone.utc,
            )
        except (OverflowError, OSError, ValueError) as exc:
            raise WeatherApiNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                (
                    f"WeatherAPI field {field_path} is not a valid "
                    "Unix timestamp."
                ),
            ) from exc

    def _unavailable(
        self,
        *,
        location: WeatherLocationRequest,
        failure_code: WeatherFailureCode,
        failure_message: str,
    ) -> LocationWeatherData:
        return LocationWeatherData(
            location_role=location.location_role,
            location_name=location.location_name,
            requested_latitude=location.latitude,
            requested_longitude=location.longitude,
            source="WEATHERAPI",
            status=WeatherDataStatus.UNAVAILABLE,
            failure_code=failure_code,
            failure_message=failure_message,
        )


class WeatherApiNormalizationError(Exception):
    def __init__(
        self,
        code: WeatherFailureCode,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ResilientWeatherProvider:
    """Try Open-Meteo first and WeatherAPI only when the primary is unusable."""

    def __init__(
        self,
        *,
        primary_provider: WeatherPairProvider,
        fallback_provider: WeatherPairProvider,
        fallback_enabled: bool,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self.fallback_enabled = fallback_enabled
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache_lock = Lock()
        self._cached_key: tuple[tuple[str, str, float, float], ...] | None = None
        self._cached_pair: (
            tuple[LocationWeatherData, LocationWeatherData] | None
        ) = None
        self._cache_expires_at = 0.0

    def fetch_locations(
        self,
        *,
        upstream: WeatherLocationRequest,
        downstream: WeatherLocationRequest,
    ) -> tuple[LocationWeatherData, LocationWeatherData]:
        locations = (upstream, downstream)
        cache_key = self._cache_key(locations)

        with self._cache_lock:
            now = monotonic()

            if (
                self.cache_ttl_seconds > 0
                and self._cached_key == cache_key
                and self._cached_pair is not None
                and now < self._cache_expires_at
            ):
                return self._copy_pair(self._cached_pair)

            primary_result = self.primary_provider.fetch_locations(
                upstream=upstream,
                downstream=downstream,
            )

            if self._is_usable_pair(primary_result):
                self._store_cache(
                    cache_key=cache_key,
                    pair=primary_result,
                    now=now,
                )
                return primary_result

            if not self.fallback_enabled:
                return primary_result

            fallback_result = self.fallback_provider.fetch_locations(
                upstream=upstream,
                downstream=downstream,
            )

            if self._is_usable_pair(fallback_result):
                self._store_cache(
                    cache_key=cache_key,
                    pair=fallback_result,
                    now=now,
                )
                return fallback_result

            if (
                self._available_count(primary_result)
                > self._available_count(fallback_result)
            ):
                return primary_result

            return fallback_result

    def _store_cache(
        self,
        *,
        cache_key: tuple[tuple[str, str, float, float], ...],
        pair: tuple[LocationWeatherData, LocationWeatherData],
        now: float,
    ) -> None:
        if self.cache_ttl_seconds <= 0:
            return

        self._cached_key = cache_key
        self._cached_pair = self._copy_pair(pair)
        self._cache_expires_at = now + self.cache_ttl_seconds

    def _is_usable_pair(
        self,
        pair: tuple[LocationWeatherData, LocationWeatherData],
    ) -> bool:
        return all(
            item.status == WeatherDataStatus.AVAILABLE
            for item in pair
        )

    def _available_count(
        self,
        pair: tuple[LocationWeatherData, LocationWeatherData],
    ) -> int:
        return sum(
            item.status == WeatherDataStatus.AVAILABLE
            for item in pair
        )

    def _cache_key(
        self,
        locations: tuple[
            WeatherLocationRequest,
            WeatherLocationRequest,
        ],
    ) -> tuple[tuple[str, str, float, float], ...]:
        return tuple(
            (
                location.location_role.value,
                location.location_name,
                location.latitude,
                location.longitude,
            )
            for location in locations
        )

    def _copy_pair(
        self,
        pair: tuple[
            LocationWeatherData,
            LocationWeatherData,
        ],
    ) -> tuple[LocationWeatherData, LocationWeatherData]:
        return (
            pair[0].model_copy(deep=True),
            pair[1].model_copy(deep=True),
        )
