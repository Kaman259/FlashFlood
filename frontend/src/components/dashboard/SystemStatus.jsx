function StatusRow({ label, value, tone = "neutral", secondary = false }) {
  const toneClass = {
    good: "text-emerald-300",
    warning: "text-yellow-200",
    bad: "text-red-300",
    neutral: "text-slate-200",
  }[tone];

  return (
    <div
      className={`grid grid-cols-[1fr_auto] gap-4 border-b border-slate-800 py-2.5 last:border-b-0 ${
        secondary ? "opacity-70" : ""
      }`}
    >
      <dt className="text-xs uppercase tracking-[0.08em] text-slate-500">
        {label}
      </dt>
      <dd className={`text-right text-sm font-bold ${toneClass}`}>{value}</dd>
    </div>
  );
}

function weatherCoverageLabel(status) {
  if (status === "FULL") return "Full";
  if (status === "PARTIAL") return "Partial";
  if (status === "UNAVAILABLE") return "Unavailable";
  return "Data unavailable";
}

function weatherCoverageTone(status) {
  if (status === "FULL") return "good";
  if (status === "PARTIAL") return "warning";
  if (status === "UNAVAILABLE") return "bad";
  return "neutral";
}

function formatTimestamp(value) {
  if (!value) return "DATA UNAVAILABLE";

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "DATA UNAVAILABLE";

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function freshnessLabel(entry) {
  if (entry?.mode === "LIVE") {
    return "Live";
  }

  if (entry?.mode === "LAST_KNOWN") {
    return `Last known — not live · Captured ${formatTimestamp(entry.savedAt)}`;
  }

  return "Unavailable";
}

function freshnessTone(entry) {
  if (entry?.mode === "LIVE") return "good";
  if (entry?.mode === "LAST_KNOWN") return "warning";
  return "neutral";
}

function operatingModeLabel(mode) {
  if (mode === "FULL_ONLINE") return "Full online";
  if (mode === "DEGRADED") return "Degraded";
  if (mode === "OFFLINE") return "Offline";
  return "Checking";
}

function operatingModeTone(mode) {
  if (mode === "FULL_ONLINE") return "good";
  if (mode === "DEGRADED") return "warning";
  return "neutral";
}

function latestWeatherTime(weather) {
  const times = [weather?.upstream?.observed_at, weather?.downstream?.observed_at]
    .filter(Boolean)
    .map((value) => new Date(value))
    .filter((value) => !Number.isNaN(value.getTime()));

  if (!times.length) return null;

  return new Date(Math.max(...times.map((value) => value.getTime())));
}

export default function SystemStatus({
  browserOnline,
  backendStatus,
  operatingMode,
  freshness,
  weather,
  telemetry,
  assessmentTimestamp,
  lastUpdated,
  refreshIntervalMs,
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="section-label">Data health</p>
          <h3 className="mt-1 text-base font-bold text-slate-100">System status</h3>
        </div>
      </div>

      <div className="panel-body">
        <dl>
          <StatusRow
            label="Operating mode"
            value={operatingModeLabel(operatingMode)}
            tone={operatingModeTone(operatingMode)}
          />
          <StatusRow
            label="Browser network"
            value={browserOnline ? "Online" : "Offline"}
            tone={browserOnline ? "good" : "warning"}
          />
          <StatusRow
            label="Backend connectivity"
            value={backendStatus === "ONLINE" ? "Online" : backendStatus === "OFFLINE" ? "Offline" : "Checking"}
            tone={backendStatus === "ONLINE" ? "good" : backendStatus === "OFFLINE" ? "warning" : "neutral"}
          />
          <StatusRow
            label="Weather data"
            value={freshnessLabel(freshness?.weather)}
            tone={freshnessTone(freshness?.weather)}
          />
          <StatusRow
            label="Telemetry data"
            value={freshnessLabel(freshness?.telemetry)}
            tone={freshnessTone(freshness?.telemetry)}
          />
          <StatusRow
            label="Risk assessment"
            value={freshnessLabel(freshness?.risk)}
            tone={freshnessTone(freshness?.risk)}
          />
          <StatusRow
            label="Weather coverage"
            value={weatherCoverageLabel(weather?.coverage_status)}
            tone={weatherCoverageTone(weather?.coverage_status)}
          />
          <StatusRow label="Weather source" value="Open-Meteo" />
          <StatusRow label="Telemetry source" value="Simulated telemetry" />
          <StatusRow
            label="Last weather update"
            value={formatTimestamp(latestWeatherTime(weather))}
          />
          <StatusRow
            label="Last telemetry update"
            value={formatTimestamp(telemetry?.timestamp)}
          />
          <StatusRow
            label="Assessment timestamp"
            value={formatTimestamp(assessmentTimestamp)}
          />
          <StatusRow
            label="Polling interval"
            value={`${Math.round(refreshIntervalMs / 1000)} s`}
            secondary
          />
          <StatusRow
            label="Dashboard refresh"
            value={lastUpdated ? lastUpdated.toLocaleTimeString() : "Not refreshed"}
            secondary
          />
        </dl>
      </div>
    </section>
  );
}