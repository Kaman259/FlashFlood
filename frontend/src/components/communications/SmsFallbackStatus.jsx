import { useEffect, useState } from "react";

import { getLatestSms } from "../../services/api.js";

function readEnabled() {
  return (
    String(import.meta.env.VITE_SMS_SIMULATOR_ENABLED ?? "")
      .trim()
      .toLowerCase() === "true"
  );
}

function humanizeTrigger(value) {
  return String(value ?? "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^\w/, (character) => character.toUpperCase());
}

export default function SmsFallbackStatus() {
  const enabled = readEnabled();
  const [refreshKey, setRefreshKey] = useState(0);
  const [state, setState] = useState({
    status: enabled ? "LOADING" : "DISABLED",
    event: null,
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let active = true;

    getLatestSms()
      .then((result) => {
        if (!active) {
          return;
        }

        setState({
          status:
            result?.status === "available"
              ? "AVAILABLE"
              : result?.status === "empty"
                ? "EMPTY"
                : "UNAVAILABLE",
          event: result?.event ?? null,
        });
      })
      .catch(() => {
        if (active) {
          setState({ status: "UNAVAILABLE", event: null });
        }
      });

    return () => {
      active = false;
    };
  }, [enabled, refreshKey]);

  const event = state.event;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="section-label">SIMULATED SMS FALLBACK</p>
          <p className="mt-1 text-[11px] font-bold text-amber-200">
            SIMULATION ONLY — NO REAL SMS SENT
          </p>
        </div>
      </div>

      <div className="panel-body">
        {state.status === "DISABLED" ? (
          <p className="status-label text-slate-300">SIMULATOR DISABLED</p>
        ) : state.status === "LOADING" ? (
          <p className="status-label text-slate-300">CHECKING SIMULATOR</p>
        ) : state.status === "UNAVAILABLE" ? (
          <p className="status-label text-slate-300">SIMULATOR UNAVAILABLE</p>
        ) : state.status === "EMPTY" ? (
          <p className="status-label text-slate-300">
            NO SIMULATED SMS RECORDED
          </p>
        ) : (
          <div className="grid gap-2 text-sm">
            <div className="communication-row">
              <span>Risk</span>
              <strong>{event?.risk_level ?? "—"}</strong>
            </div>
            <div className="communication-row">
              <span>Trigger</span>
              <strong>{humanizeTrigger(event?.trigger_type)}</strong>
            </div>
            <div className="communication-row">
              <span>Status</span>
              <strong>{event?.delivery_status ?? "—"}</strong>
            </div>
            <div className="communication-row">
              <span>Time</span>
              <strong>
                {event?.created_at
                  ? new Date(event.created_at).toLocaleString()
                  : "—"}
              </strong>
            </div>
            <div className="communication-row">
              <span>Demo recipient</span>
              <strong>{event?.recipient_reference ?? "—"}</strong>
            </div>

            <div className="mt-3 border-l-2 border-amber-500 bg-amber-950/20 px-3 py-2">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-amber-200">
                Simulated message
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-200">
                {event?.message_body ?? "No simulated message available."}
              </p>
            </div>
          </div>
        )}

        {enabled && (
          <button
            type="button"
            className="command-button mt-4"
            disabled={state.status === "LOADING"}
            onClick={() => setRefreshKey((current) => current + 1)}
          >
            REFRESH SIMULATOR
          </button>
        )}
      </div>
    </section>
  );
}