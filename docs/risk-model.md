# FlashFlood Prototype Risk Model

FlashFlood receives five raw environmental measurements:

1. `live_rainfall_intensity_mm_per_hour`
2. `forecast_rainfall_intensity_mm_per_hour`
3. `river_level_m`
4. `river_change_m_per_hour`
5. `upstream_discharge_m3_per_s`

These produce four scored severity signals:

1. derived rainfall severity
2. river-level severity
3. river-level-change severity
4. upstream-discharge severity

Live and forecast rainfall are not scored separately.

## Source-aware rainfall

Live rainfall and forecast rainfall are classified independently.

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

Examples:

- forecast 40, live 10 -> YELLOW
- forecast 40, live 35 -> ORANGE
- forecast 40, live 55 -> RED

Both source classifications remain available for explanation, but only the derived rainfall severity enters scoring.

The forecast time horizon and forecast-value selection rule are intentionally not defined at this stage. They will be specified when the weather provider is integrated because the submitted project specification does not define a forecast horizon.

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

A real deployment requires locally validated rainfall criteria and river-level, change-rate, and discharge limits appropriate to the monitoring station, river basin, data source, and responsible authorities.
