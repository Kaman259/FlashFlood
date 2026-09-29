# FlashFlood Screenshot Capture Plan

This directory is reserved for **real screenshots captured from the running FlashFlood application**.

Do not add generated, mocked, AI-created, or fabricated interface images.

## Recommended screenshots

1. **Main command center — FULL ONLINE**
   - Show dashboard, weather/telemetry/risk, map, and system status.
   - `command-center-online.png`

2. **Critical risk state**
   - Show `RED — DANGER`, risk score, warning reasons, and recommended action.
   - `critical-risk.png`

3. **Simulated SMS fallback**
   - Show `SIMULATED SMS FALLBACK`, generated message, timestamp/status, and the no-real-SMS notice.
   - `simulated-sms.png`

4. **Emergency report panel**
   - Show the prototype form and the notice that it does not contact emergency services.
   - `emergency-report.png`

5. **DEGRADED mode**
   - Browser online, backend stopped; show `Network: ONLINE`, `Backend: OFFLINE`, `DEGRADED`, and last-known data.
   - `degraded-mode.png`

6. **Browser OFFLINE with cached data**
   - Show `OFFLINE`, `LAST KNOWN — NOT LIVE`, and captured timestamps.
   - `offline-last-known.png`

7. **Offline map with cached tiles**
   - Capture a previously loaded map area while offline.
   - `offline-map-cache.png`

8. **Recovery to FULL ONLINE**
   - Restore network/backend and show stale labels replaced by live data.
   - `recovery-full-online.png`

## README shortlist

Use only four screenshots in the main README unless a fifth adds clear value:

1. `command-center-online.png`
2. `critical-risk.png`
3. `simulated-sms.png`
4. `offline-last-known.png`

Optional fifth: `recovery-full-online.png`.

## Capture guidelines

- Use real application state only.
- Hide personal notifications, unrelated tabs, bookmarks, and local filesystem paths.
- Do not expose `.env` values or credentials.
- Keep browser size and zoom consistent.
- Prefer PNG.
- Do not present optional Firebase/FCM cloud behavior as connected when it is not.
