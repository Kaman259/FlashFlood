# Simulated River Telemetry

FlashFlood currently uses deterministic simulated upstream river telemetry for demonstration and testing. It does not represent a live sensor network or real river measurements.

## Telemetry fields

- `timestamp`: fixed UTC time assigned to the demo record
- `station_id`: simulated upstream monitoring-station identifier
- `river_level_m`: river level in metres relative to the demo station datum
- `river_change_m_per_hour`: rate of river-level change in metres per hour
- `upstream_discharge_m3_per_s`: simulated upstream discharge in cubic metres per second
- `scenario`: selected demonstration scenario
- `data_source`: always `SIMULATED_DEMONSTRATION`

## Demo scenarios

| Scenario | River level | Change rate | Upstream discharge |
| --- | ---: | ---: | ---: |
| normal | 1.20 m | 0.02 m/hour | 100 m3/s |
| watch | 2.20 m | 0.15 m/hour | 250 m3/s |
| moderate-surge | 3.20 m | 0.35 m/hour | 500 m3/s |
| critical-surge | 4.40 m | 0.75 m/hour | 900 m3/s |

All values in this table are fixed simulated demonstration data.

They are not real measurements, hydrological forecasts, or scientifically calibrated warning thresholds.

## API

`GET /api/telemetry/latest`

Returns the currently selected simulated telemetry record.

`GET /api/telemetry/demo/{scenario}`

Selects one of:

- `normal`
- `watch`
- `moderate-surge`
- `critical-surge`

The selected state is stored only in application memory and resets to `normal` when the backend restarts.

## Risk-engine connection

Telemetry does not contain risk calculations.

The integration flow is:

Telemetry record
+
rainfall input
->
`telemetry_to_risk_request()`
->
`RiskAssessmentRequest`
->
existing risk service

The telemetry adapter supplies:

- river level
- river-level change
- upstream discharge
- station ID

Live rainfall and forecast rainfall remain separate inputs so the telemetry service does not become responsible for weather data.

The risk service classifies upstream discharge using centralized prototype demo-station thresholds together with rainfall, river level, and river-level change.

A real deployment would replace the simulated telemetry with validated station or sensor data and locally calibrated hydrological thresholds.


