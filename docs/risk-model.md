# FlashFlood Prototype Risk Model

At the risk-service boundary, FlashFlood receives five environmental inputs:

1. `live_rainfall_intensity_mm_per_hour`
2. `forecast_rainfall_intensity_mm_per_hour`
3. `river_level_m`
4. `river_change_m_per_hour`
5. `upstream_discharge_m3_per_s`

In Stage 5, the two rainfall inputs are aggregated from two prototype weather locations before they reach the risk service:

- Mokokchung, Nagaland, India: upstream weather location
- Sonari, Charaideo, Assam, India: downstream weather/study area

For each source type:

`live_rainfall_input = max(upstream_live, downstream_live)`

`forecast_rainfall_input = max(upstream_forecast, downstream_forecast)`

The locations are not added or averaged, so a severe value at one location is not hidden or double counted.

These rainfall inputs plus the three river measurements still produce only four scored severity signals:

1. derived rainfall severity
2. river-level severity
3. river-level-change severity
4. upstream-discharge severity

Live and forecast rainfall are not scored separately, and upstream/downstream rainfall are not scored separately.

## Source-aware rainfall

Live rainfall and forecast rainfall are classified independently after the two-location weather aggregation.

### Forecast rainfall

- GREEN: 30 mm/hour or below
- YELLOW: above 30 mm/hour

The comparison is strict.

Examples:

- 30.00 mm/hour -> GREEN
- 30.01 mm/hour -> YELLOW

### Live rainfall

- GREEN: 30 mm/hour or below
- ORANGE: above 30 and up to and including 50 mm/hour
- RED: above 50 mm/hour

There is deliberately no live-rainfall YELLOW band.

Examples:

- 30.00 mm/hour -> GREEN
- 30.01 mm/hour -> ORANGE
- 50.00 mm/hour -> ORANGE
- 50.01 mm/hour -> RED

### Derived rainfall severity

The single rainfall signal used by the risk model is:

`rainfall_severity = max(live_rainfall_severity, forecast_rainfall_severity)`

Example:

- upstream forecast 40, downstream forecast 20
- upstream live 10, downstream live 35
- aggregated forecast = 40 -> YELLOW
- aggregated live = 35 -> ORANGE
- derived rainfall severity = ORANGE

Only this one derived rainfall severity enters the four-signal score.

### Forecast horizon

Stage 5 uses the **peak forecast hourly rainfall within the selected six-hour prototype window**.

The six-hour window is an explicit prototype choice and is not claimed to be scientifically optimal.

See `docs/weather.md` for the exact Open-Meteo interval-selection and unit-conversion rules.

## Demo-station river level

- GREEN: below 2.0 m
- YELLOW: 2.0 to below 3.0 m
- ORANGE: 3.0 to below 4.0 m
- RED: 4.0 m or higher

## River-level change

- GREEN: below 0.10 m/hour
- YELLOW: 0.10 to below 0.30 m/hour
- ORANGE: 0.30 to below 0.60 m/hour
- RED: 0.60 m/hour or higher

A negative change represents a falling river and is GREEN for this signal.

## Demo-station upstream discharge

- GREEN: below 200 m3/s
- YELLOW: 200 to below 400 m3/s
- ORANGE: 400 to below 800 m3/s
- RED: 800 m3/s or higher

## Scoring

The four scored severities are sorted:

`D >= S1 >= S2 >= S3`

Only the dominant signal and two strongest supporting signals contribute:

`score = (25 x D) + (4 x S1) + (4 x S2)`

`S3` contributes zero numeric points but remains available for explanation and reason generation.

The natural maximum score is:

`75 + 12 + 12 = 99`

No artificial adjustment to 100 is applied.

## Risk bands

- 0 to 24: GREEN
- 25 to 49: YELLOW
- 50 to 74: ORANGE
- 75 to 100: RED

## Why only two supporting signals contribute

River level, river-level change, and upstream discharge can represent related parts of the same hydrological event.

Restricting numeric support to the two strongest supporting signals reduces repeated contribution from related indicators.

An elevated fourth signal can still become D, S1, or S2 when its severity is stronger than another signal.

## Prototype limitation

These rules and thresholds are for educational and demonstration use.

They must not be treated as universal or scientifically calibrated flood-warning limits.

The Mokokchung and Sonari coordinates are prototype study locations. They are not presented as a scientifically validated hydrological pathway between the two exact points.

A real deployment requires locally validated rainfall criteria and river-level, change-rate, and discharge limits appropriate to the monitoring station, river basin, data source, and responsible authorities.