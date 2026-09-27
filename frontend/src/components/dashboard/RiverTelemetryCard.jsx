function formatTimestamp(value) {
  if (!value) {
    return "DATA UNAVAILABLE";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "DATA UNAVAILABLE";
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function valueOrUnavailable(value, suffix) {
  if (value == null) {
    return "DATA UNAVAILABLE";
  }

  return `${Number(value).toFixed(2)} ${suffix}`;
}

function humanizeScenario(value) {
  if (!value) return "DATA UNAVAILABLE";

  return String(value)
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function RiverTelemetryCard({ telemetry, error, freshness }) {
  const lastKnown = freshness?.mode === "LAST_KNOWN";
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="section-label">River telemetry</p>
          <h3 className="mt-1 text-base font-bold text-slate-100">
            Upstream monitoring station
          </h3>
        </div>

        <span className="status-label border-amber-500/60 text-amber-100">
          {lastKnown ? "LAST KNOWN — NOT LIVE" : "SIMULATED TELEMETRY"}
        </span>
      </div>

      <div className="panel-body">
        {error && (
          <div className="mb-4 border-l-2 border-red-500 bg-red-950/25 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        )}

        <dl className="data-grid sm:grid-cols-2 xl:grid-cols-3">
          <div className="data-cell">
            <dt className="data-label">{lastKnown ? "Last-known river level" : "River level"}</dt>
            <dd className="data-value">
              {valueOrUnavailable(telemetry?.river_level_m, "m")}
            </dd>
          </div>

          <div className="data-cell">
            <dt className="data-label">{lastKnown ? "Last-known change rate" : "Change rate"}</dt>
            <dd className="data-value">
              {valueOrUnavailable(telemetry?.river_change_m_per_hour, "m/hour")}
            </dd>
          </div>

          <div className="data-cell">
            <dt className="data-label">{lastKnown ? "Last-known discharge" : "Upstream discharge"}</dt>
            <dd className="data-value">
              {valueOrUnavailable(telemetry?.upstream_discharge_m3_per_s, "m3/s")}
            </dd>
          </div>

          <div className="data-cell">
            <dt className="data-label">Station ID</dt>
            <dd className="data-value text-sm">
              {telemetry?.station_id ?? "DATA UNAVAILABLE"}
            </dd>
          </div>

          <div className="data-cell">
            <dt className="data-label">Scenario</dt>
            <dd className="data-value text-sm">
              {humanizeScenario(telemetry?.scenario)}
            </dd>
          </div>

          <div className="data-cell">
            <dt className="data-label">Last telemetry update</dt>
            <dd className="data-value text-sm">
              {formatTimestamp(telemetry?.timestamp)}
            </dd>
          </div>
        </dl>

        <p className="mt-4 text-xs leading-5 text-slate-500">
          Source: <span className="font-semibold text-slate-300">Simulated telemetry</span>
        </p>

        {lastKnown && (
          <div className="mt-3 border-l-2 border-amber-500 bg-amber-950/20 px-3 py-2 text-xs leading-5 text-amber-100">
            LAST KNOWN — NOT LIVE · Captured: {formatTimestamp(freshness?.savedAt)}
          </div>
        )}
      </div>
    </section>
  );
}