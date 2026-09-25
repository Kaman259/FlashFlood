# Open-Meteo Weather Integration

FlashFlood uses Open-Meteo as the prototype external rainfall-data provider for two study locations:

- Upstream: Mokokchung, Nagaland, India
  - Latitude: `26.31393`
  - Longitude: `94.51675`
- Downstream: Sonari, Charaideo, Assam, India
  - Latitude: `27.0280`
  - Longitude: `95.0312`

These are prototype study locations. They are not presented as a validated river-gauge pair or as a scientifically modelled hydrological pathway between the two exact points.

The simulated river telemetry remains demonstration data.

## Open-Meteo request

The provider uses the official Forecast API:

`https://api.open-meteo.com/v1/forecast`

For each location it requests:

- `latitude`
- `longitude`
- `current=rain,showers`
- `hourly=rain,showers`
- `precipitation_unit=mm`
- `timezone=GMT`
- `forecast_hours=WEATHER_FORECAST_HORIZON_HOURS + 2`

With the default six-hour prototype horizon, this produces `forecast_hours=8`.

The two extra hourly records allow the provider to exclude the current or incomplete hourly period while still selecting six complete future one-hour intervals.

## Live rainfall

For each location:

`current_rainfall_mm = current.rain + current.showers`

The current rainfall fields are treated as accumulated values for the returned `current.interval`.

FlashFlood converts them into an:

**EQUIVALENT HOURLY INTENSITY derived from the current model interval.**

The calculation is:

`live_rainfall_intensity_mm_per_hour = (current.rain + current.showers) Ã— 3600 / current.interval`

For example, 1.5 mm during a 900-second interval becomes:

`1.5 Ã— 3600 / 900 = 6.0 mm/hour`

This is not described as a directly observed one-hour accumulation.

A missing, zero, or negative interval is invalid provider data. It is not converted to rainfall.

## Forecast rainfall

Open-Meteo hourly `rain` and `showers` values are preceding-hour sums in millimetres.

For every selected future hour:

`hourly_rainfall_mm = hourly.rain + hourly.showers`

Because each selected interval is exactly one hour, the numeric value is used as the hourly rainfall intensity for that one-hour period.

FlashFlood stores the:

**peak forecast hourly rainfall within the selected six-hour prototype window**

as:

`forecast_rainfall_intensity_mm_per_hour = max(six selected hourly rainfall values)`

The six-hour horizon is a prototype choice. It is not claimed to be scientifically optimal.

## Complete future interval selection

The provider uses the returned `current.time`.

Example:

- current time: `11:45 GMT`
- next full-hour boundary: `12:00 GMT`

The selected intervals are:

- 12:00â€“13:00
- 13:00â€“14:00
- 14:00â€“15:00
- 15:00â€“16:00
- 16:00â€“17:00
- 17:00â€“18:00

Because the hourly rainfall value is a preceding-hour sum, these intervals use hourly response timestamps ending at:

- 13:00
- 14:00
- 15:00
- 16:00
- 17:00
- 18:00

The incomplete/current interval is excluded.

`forecast_peak_time` stores the response timestamp for the selected maximum. If multiple values tie, the earliest timestamp is used.

If all six expected complete future hourly intervals are not present, that location becomes `UNAVAILABLE` with `INSUFFICIENT_FORECAST_DATA`. The horizon is never silently shortened.

## Normalized location data

Open-Meteo JSON is normalized before it leaves the provider layer.

Each location record contains:

- location role
- location name
- requested latitude and longitude
- provider latitude and longitude
- source
- availability status
- observation timestamp
- live rainfall equivalent hourly intensity
- forecast peak hourly rainfall
- forecast horizon
- forecast window start
- forecast window end
- forecast peak time
- rainfall unit
- current interval
- structured failure code and message when unavailable

Raw Open-Meteo arrays are not exposed by the public weather API.

## Two-location aggregation

Upstream and downstream weather are fetched independently and normalized independently.

When both are available:

`aggregated_live = max(upstream_live, downstream_live)`

`aggregated_forecast = max(upstream_forecast, downstream_forecast)`

The system never adds or averages the locations.

It also records:

- `live_driver_locations`
- `forecast_driver_locations`

If both locations have the same maximum value, both are retained as drivers.

The aggregation does not perform flood scoring.

## Risk integration

When weather coverage is `FULL`, the aggregated rainfall values feed the existing risk request:

- `live_rainfall_intensity_mm_per_hour = aggregated_live`
- `forecast_rainfall_intensity_mm_per_hour = aggregated_forecast`

Simulated telemetry supplies:

- river level
- river change rate
- upstream discharge
- station ID

The existing risk service then derives one rainfall severity and combines it with the three river-related signals.

The Stage 4 scoring mathematics remains unchanged.

## Coverage and failure behavior

Weather coverage is:

- `FULL`: both locations available
- `PARTIAL`: exactly one location available
- `UNAVAILABLE`: neither location available

Only `FULL` weather coverage is allowed to construct a complete automated `RiskAssessmentRequest`.

`PARTIAL` data can be returned for inspection, but `risk_input_ready` is `false`.

If both locations are unavailable, `GET /api/weather` returns HTTP 503 with the normalized unavailable snapshot.

Structured failure codes include:

- `TIMEOUT`
- `CONNECTION_FAILURE`
- `HTTP_ERROR`
- `MALFORMED_RESPONSE`
- `MISSING_FIELD`
- `INVALID_UNIT`
- `INSUFFICIENT_FORECAST_DATA`
- `INVALID_CONFIGURATION`

A provider failure is never converted to zero rainfall.

`0 mm/hour` means a successful provider response reporting zero rainfall.

`UNAVAILABLE` means the rainfall state is unknown.

## Configuration

The default prototype configuration is:

```text
WEATHER_UPSTREAM_LATITUDE=26.31393
WEATHER_UPSTREAM_LONGITUDE=94.51675
WEATHER_DOWNSTREAM_LATITUDE=27.0280
WEATHER_DOWNSTREAM_LONGITUDE=95.0312
WEATHER_FORECAST_HORIZON_HOURS=6
WEATHER_TIMEOUT_SECONDS=5
```

Latitude, longitude, horizon, and timeout values are validated by application configuration.

Open-Meteo does not require an API key for this prototype.

## Public API

`GET /api/weather`

The endpoint returns normalized two-location weather information.

It does not expose uncontrolled raw Open-Meteo JSON.

## Prototype limitation

Open-Meteo provides weather-model data. The weather response itself is not a flood prediction.

The rainfall thresholds, six-hour forecast window, study locations, simulated river telemetry, and risk model are prototype choices for educational and demonstration use.

A real deployment would require locally validated hydrological relationships, calibrated warning thresholds, and review by responsible authorities.