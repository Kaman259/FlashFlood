# FlashFlood Portfolio Demo

This demo is designed for a short college/project presentation. It demonstrates existing behavior without claiming operational flood-warning capability.

## Preparation

Open two terminals.

### Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm run dev
```

Open the Vite URL shown in the terminal.

For the free local SMS demo, use:

Backend `.env`:

```text
FIRESTORE_ENABLED=false
FCM_ENABLED=false
SMS_SIMULATOR_ENABLED=true
EMERGENCY_REPORTING_ENABLED=false
```

Frontend `.env`:

```text
VITE_SMS_SIMULATOR_ENABLED=true
VITE_EMERGENCY_REPORTING_ENABLED=false
```

Restart both development servers after changing environment files.

## Demo 1 — Normal Conditions

### What to click

Select:

```text
NORMAL
```

or start from a fresh backend, where the selected telemetry scenario defaults to normal.

### What should appear

- simulated river telemetry at normal values,
- backend risk assessment,
- weather data from Open-Meteo when available,
- `FULL ONLINE` when browser, backend, and required live feeds are available.

### What this demonstrates

The frontend requests current weather + telemetry and asks the FastAPI backend for the authoritative risk result.

The frontend does not map `normal` directly to a risk label.

## Demo 2 — Watch / Warning Conditions

### What to click

Try:

```text
WATCH
MODERATE SURGE
```

### What should appear

Telemetry changes immediately after the backend returns the selected scenario.

With ordinary valid weather inputs, the backend demonstration commonly produces:

- WATCH -> elevated/YELLOW behavior,
- MODERATE SURGE -> ORANGE/WARNING behavior.

Weather still participates in the backend request, so the UI does not hard-code these labels.

### What this demonstrates

A deterministic telemetry change flows through the real backend risk engine rather than a frontend-only animation.

## Demo 3 — Critical Simulated Event

### What to click

Make sure at least one lower-severity live assessment has already occurred, then select:

```text
CRITICAL SURGE
```

### What should appear

- critical simulated river telemetry,
- RED / DANGER backend risk,
- risk score,
- warning reasons,
- recommended action.

### What this demonstrates

A live risk transition is generated from the backend using the same risk engine used by every other scenario.

## Demo 4 — Local Simulated SMS Fallback

### Before the demo

Use the free local SMS environment settings from the Preparation section.

Do **not** enable Firestore or FCM for this demo.

### What to click

1. Start/restart the backend.
2. Load the dashboard so a lower-severity live assessment establishes the in-memory baseline.
3. Select `CRITICAL SURGE`.
4. In the SMS panel, click `REFRESH SIMULATOR`.

### What should appear

The panel is explicitly labelled:

```text
SIMULATED SMS FALLBACK
SIMULATION ONLY — NO REAL SMS SENT
```

A successful local fallback demonstration shows:

- risk: RED,
- trigger: FCM disabled fallback,
- status: `SIMULATED_DELIVERED`,
- timestamp,
- generated server-controlled message,
- simulated recipient reference.

### What this demonstrates

The backend created a demonstration fallback record. No telecom service is called and no real phone number is used.

Repeated RED polling does not create a new escalation event unless the live severity first falls and later rises again.

## Demo 5 — Backend Failure / Degraded Mode

### What to do

Keep the browser network online, but stop FastAPI with `Ctrl + C`.

Then click:

```text
Refresh data
```

### What should appear

- `Network: ONLINE`
- `Backend: OFFLINE`
- operating mode `DEGRADED`
- valid cached weather/telemetry/risk may remain visible as `LAST KNOWN — NOT LIVE`
- captured timestamps remain the original IndexedDB `savedAt`.

### What this demonstrates

Browser connectivity and backend reachability are separate states.

No stale data is silently presented as live.

## Demo 6 — Browser Offline

### What to do

In browser DevTools:

```text
Network -> Offline
```

Reload the application.

### What should appear

- application shell still loads if previously cached,
- operating mode `OFFLINE`,
- last-known weather/telemetry/risk if previously cached,
- `LAST KNOWN — NOT LIVE` freshness labels,
- prototype polygon and shelter overlays,
- previously cached OSM tiles where available.

Uncached map tiles may be blank. That is expected.

### What this demonstrates

FlashFlood offers degraded display availability, not an offline decision engine.

The browser does not calculate a new risk from cached data and does not trigger SMS/FCM from cached risk.

## Demo 7 — Recovery

### What to do

1. Restore browser network connectivity.
2. Restart FastAPI if it is stopped.
3. Click `Refresh data` or wait for the normal refresh interval.

### What should appear

- `Network: ONLINE`,
- `Backend: ONLINE`,
- `FULL ONLINE` after required live data returns,
- `LIVE` replaces `LAST KNOWN — NOT LIVE`,
- map tiles resume normal network loading.

### What this demonstrates

Cached display data is replaced by valid fresh backend data after recovery.

## Emergency-Reporting Panel

The panel is useful for explaining API validation and prototype boundaries, but with Firebase/Firestore intentionally unconfigured it should remain unavailable.

It does **not** contact emergency services.

Do not present it as a completed real-world emergency dispatch integration.

## Suggested Closing Statement

> FlashFlood demonstrates an explainable monitoring architecture with live weather, simulated river telemetry, backend risk evaluation, controlled communication simulation, and safe degraded/offline display behavior. It is an educational prototype, not an operational flood-warning or emergency-response system.
