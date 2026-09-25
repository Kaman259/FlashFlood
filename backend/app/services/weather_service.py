from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

import httpx

from app.models.weather import (
    LocationWeatherData,
    WeatherDataStatus,
    WeatherFailureCode,
    WeatherLocationRole,
)


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherNormalizationError(Exception):
    def __init__(
        self,
        code: WeatherFailureCode,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OpenMeteoWeatherProvider:
    def __init__(
        self,
        *,
        forecast_horizon_hours: int,
        timeout_seconds: float,
    ) -> None:
        self.forecast_horizon_hours = forecast_horizon_hours
        self.timeout_seconds = timeout_seconds

    def fetch_location(
        self,
        *,
        location_role: WeatherLocationRole,
        location_name: str,
        latitude: float,
        longitude: float,
    ) -> LocationWeatherData:
        configuration_error = self._validate_configuration(
            latitude=latitude,
            longitude=longitude,
        )
        if configuration_error is not None:
            return self._unavailable(
                location_role=location_role,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                failure_code=WeatherFailureCode.INVALID_CONFIGURATION,
                failure_message=configuration_error,
            )

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "rain,showers",
            "hourly": "rain,showers",
            "precipitation_unit": "mm",
            "timezone": "GMT",
            "forecast_hours": self.forecast_horizon_hours + 2,
        }

        try:
            response = httpx.get(
                OPEN_METEO_FORECAST_URL,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            return self._unavailable(
                location_role=location_role,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                failure_code=WeatherFailureCode.TIMEOUT,
                failure_message="Open-Meteo request timed out.",
            )
        except httpx.ConnectError:
            return self._unavailable(
                location_role=location_role,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                failure_code=WeatherFailureCode.CONNECTION_FAILURE,
                failure_message="Could not connect to Open-Meteo.",
            )
        except httpx.HTTPStatusError as exc:
            return self._unavailable(
                location_role=location_role,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                failure_code=WeatherFailureCode.HTTP_ERROR,
                failure_message=(
                    f"Open-Meteo returned HTTP {exc.response.status_code}."
                ),
            )
        except httpx.RequestError:
            return self._unavailable(
                location_role=location_role,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                failure_code=WeatherFailureCode.CONNECTION_FAILURE,
                failure_message="Open-Meteo request failed.",
            )

        try:
            payload = response.json()
        except ValueError:
            return self._unavailable(
                location_role=location_role,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                failure_code=WeatherFailureCode.MALFORMED_RESPONSE,
                failure_message="Open-Meteo returned malformed JSON.",
            )

        try:
            return self._normalize_payload(
                payload=payload,
                location_role=location_role,
                location_name=location_name,
                requested_latitude=latitude,
                requested_longitude=longitude,
            )
        except WeatherNormalizationError as exc:
            return self._unavailable(
                location_role=location_role,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                failure_code=exc.code,
                failure_message=exc.message,
            )

    def _validate_configuration(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> str | None:
        if not -90 <= latitude <= 90:
            return "Latitude must be between -90 and 90."
        if not -180 <= longitude <= 180:
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
        location_role: WeatherLocationRole,
        location_name: str,
        requested_latitude: float,
        requested_longitude: float,
    ) -> LocationWeatherData:
        if not isinstance(payload, dict):
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "Open-Meteo response must be a JSON object.",
            )

        provider_latitude = self._required_number(payload, "latitude")
        provider_longitude = self._required_number(payload, "longitude")

        if not -90 <= provider_latitude <= 90:
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "Open-Meteo provider latitude is outside the valid range.",
            )
        if not -180 <= provider_longitude <= 180:
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "Open-Meteo provider longitude is outside the valid range.",
            )

        current = self._required_dict(payload, "current")
        current_units = self._required_dict(payload, "current_units")
        hourly = self._required_dict(payload, "hourly")
        hourly_units = self._required_dict(payload, "hourly_units")

        self._validate_units(current_units, hourly_units)

        current_time = self._parse_timestamp(
            self._required_value(current, "time")
        )

        interval = self._required_number(current, "interval")
        if interval <= 0:
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "current.interval must be greater than zero.",
            )

        current_rain = self._required_non_negative_number(
            current,
            "rain",
        )
        current_showers = self._required_non_negative_number(
            current,
            "showers",
        )

        live_intensity = (
            (current_rain + current_showers)
            * 3600.0
            / interval
        )

        times = self._required_list(hourly, "time")
        rains = self._required_list(hourly, "rain")
        showers = self._required_list(hourly, "showers")

        if not (len(times) == len(rains) == len(showers)):
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "Hourly time, rain, and showers arrays must have equal lengths.",
            )

        hourly_values: dict[datetime, float] = {}

        for raw_time, raw_rain, raw_showers in zip(
            times,
            rains,
            showers,
        ):
            timestamp = self._parse_timestamp(raw_time)

            if timestamp in hourly_values:
                raise WeatherNormalizationError(
                    WeatherFailureCode.MALFORMED_RESPONSE,
                    "Hourly response contains duplicate timestamps.",
                )

            rain = self._coerce_non_negative_number(
                raw_rain,
                field_name="hourly.rain",
            )
            shower = self._coerce_non_negative_number(
                raw_showers,
                field_name="hourly.showers",
            )

            hourly_values[timestamp] = rain + shower

        next_hour_boundary = current_time.replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        if current_time > next_hour_boundary:
            next_hour_boundary += timedelta(hours=1)

        expected_end_times = [
            next_hour_boundary + timedelta(hours=offset)
            for offset in range(
                1,
                self.forecast_horizon_hours + 1,
            )
        ]

        if any(
            timestamp not in hourly_values
            for timestamp in expected_end_times
        ):
            raise WeatherNormalizationError(
                WeatherFailureCode.INSUFFICIENT_FORECAST_DATA,
                (
                    "Open-Meteo did not provide all complete future hourly "
                    "intervals required by the configured forecast horizon."
                ),
            )

        selected_values = [
            (timestamp, hourly_values[timestamp])
            for timestamp in expected_end_times
        ]

        peak_time, peak_value = selected_values[0]
        for timestamp, value in selected_values[1:]:
            if value > peak_value:
                peak_time = timestamp
                peak_value = value

        return LocationWeatherData(
            location_role=location_role,
            location_name=location_name,
            requested_latitude=requested_latitude,
            requested_longitude=requested_longitude,
            provider_latitude=provider_latitude,
            provider_longitude=provider_longitude,
            status=WeatherDataStatus.AVAILABLE,
            observed_at=current_time,
            live_rainfall_intensity_mm_per_hour=live_intensity,
            forecast_rainfall_intensity_mm_per_hour=peak_value,
            forecast_horizon_hours=self.forecast_horizon_hours,
            forecast_window_start=next_hour_boundary,
            forecast_window_end=(
                next_hour_boundary
                + timedelta(hours=self.forecast_horizon_hours)
            ),
            forecast_peak_time=peak_time,
            rainfall_unit="mm/hour",
            current_interval_seconds=interval,
        )

    def _validate_units(
        self,
        current_units: dict[str, Any],
        hourly_units: dict[str, Any],
    ) -> None:
        required_current_units = {
            "interval": "seconds",
            "rain": "mm",
            "showers": "mm",
        }
        required_hourly_units = {
            "rain": "mm",
            "showers": "mm",
        }

        for field, expected in required_current_units.items():
            if field not in current_units:
                raise WeatherNormalizationError(
                    WeatherFailureCode.MISSING_FIELD,
                    f"Missing Open-Meteo current unit for {field}.",
                )
            if current_units[field] != expected:
                raise WeatherNormalizationError(
                    WeatherFailureCode.INVALID_UNIT,
                    (
                        f"Open-Meteo current unit for {field} must be "
                        f"{expected}."
                    ),
                )

        for field, expected in required_hourly_units.items():
            if field not in hourly_units:
                raise WeatherNormalizationError(
                    WeatherFailureCode.MISSING_FIELD,
                    f"Missing Open-Meteo hourly unit for {field}.",
                )
            if hourly_units[field] != expected:
                raise WeatherNormalizationError(
                    WeatherFailureCode.INVALID_UNIT,
                    (
                        f"Open-Meteo hourly unit for {field} must be "
                        f"{expected}."
                    ),
                )

    def _required_dict(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> dict[str, Any]:
        if field_name not in payload:
            raise WeatherNormalizationError(
                WeatherFailureCode.MISSING_FIELD,
                f"Missing Open-Meteo field: {field_name}.",
            )
        value = payload[field_name]
        if not isinstance(value, dict):
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"Open-Meteo field {field_name} must be an object.",
            )
        return value

    def _required_list(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> list[Any]:
        if field_name not in payload:
            raise WeatherNormalizationError(
                WeatherFailureCode.MISSING_FIELD,
                f"Missing Open-Meteo field: hourly.{field_name}.",
            )
        value = payload[field_name]
        if not isinstance(value, list):
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"Open-Meteo field hourly.{field_name} must be a list.",
            )
        return value

    def _required_value(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> Any:
        if field_name not in payload:
            raise WeatherNormalizationError(
                WeatherFailureCode.MISSING_FIELD,
                f"Missing Open-Meteo field: {field_name}.",
            )
        return payload[field_name]

    def _required_number(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> float:
        value = self._required_value(payload, field_name)
        return self._coerce_number(
            value,
            field_name=field_name,
        )

    def _required_non_negative_number(
        self,
        payload: dict[str, Any],
        field_name: str,
    ) -> float:
        value = self._required_value(payload, field_name)
        return self._coerce_non_negative_number(
            value,
            field_name=field_name,
        )

    def _coerce_number(
        self,
        value: Any,
        *,
        field_name: str,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
        ):
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"Open-Meteo field {field_name} must be numeric.",
            )
        return float(value)

    def _coerce_non_negative_number(
        self,
        value: Any,
        *,
        field_name: str,
    ) -> float:
        number = self._coerce_number(
            value,
            field_name=field_name,
        )
        if number < 0:
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"Open-Meteo field {field_name} cannot be negative.",
            )
        return number

    def _parse_timestamp(
        self,
        value: Any,
    ) -> datetime:
        if not isinstance(value, str):
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                "Open-Meteo timestamp must be an ISO 8601 string.",
            )

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise WeatherNormalizationError(
                WeatherFailureCode.MALFORMED_RESPONSE,
                f"Malformed Open-Meteo timestamp: {value}.",
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)

        return parsed

    def _unavailable(
        self,
        *,
        location_role: WeatherLocationRole,
        location_name: str,
        latitude: float,
        longitude: float,
        failure_code: WeatherFailureCode,
        failure_message: str,
    ) -> LocationWeatherData:
        return LocationWeatherData(
            location_role=location_role,
            location_name=location_name,
            requested_latitude=latitude,
            requested_longitude=longitude,
            status=WeatherDataStatus.UNAVAILABLE,
            failure_code=failure_code,
            failure_message=failure_message,
        )