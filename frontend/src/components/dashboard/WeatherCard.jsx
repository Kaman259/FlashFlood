function formatNumber(value) {
  if (value == null) {
    return "DATA UNAVAILABLE";
  }

  return `${Number(value).toFixed(2)} mm/hour`;
}

function formatTime(value) {
  if (!value) {
    return "DATA UNAVAILABLE";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "DATA UNAVAILABLE";
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function humanizeSource(source) {
  if (source === "OPEN_METEO") {
    return "Open-Meteo";
  }

  return source ? String(source).replaceAll("_", " ") : "DATA UNAVAILABLE";
}

function humanizeStatus(status) {
  if (status === "AVAILABLE") return "Available";
  if (status === "UNAVAILABLE") return "Data unavailable";
  return "Data unavailable";
}

export default function WeatherCard({
  title,
  subtitle,
  weather,
  role,
  liveDrivers = [],
  forecastDrivers = [],
  freshness,
}) {
  const available = weather?.status === "AVAILABLE";
  const liveDriver = liveDrivers.includes(role);
  const forecastDriver = forecastDrivers.includes(role);
  const lastKnown = freshness?.mode === "LAST_KNOWN";

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="section-label">{title}</p>
          <h3 className="mt-1 text-base font-bold text-slate-100">{subtitle}</h3>
        </div>

        <span
          className={`status-label ${
            lastKnown
              ? "border-amber-500/60 text-amber-100"
              : available
                ? "border-emerald-600/60 text-emerald-200"
                : "border-red-600/60 text-red-200"
          }`}
        >
          {lastKnown ? "LAST KNOWN — NOT LIVE" : humanizeStatus(weather?.status)}
        </span>
      </div>

      <div className="panel-body">
        <dl className="data-grid sm:grid-cols-2">
          <div className="data-cell">
            <dt className="data-label">{lastKnown ? "Last-known rainfall" : "Live rainfall"}</dt>
            <dd className="data-value">
              {available
                ? formatNumber(weather.live_rainfall_intensity_mm_per_hour)
                : "DATA UNAVAILABLE"}
            </dd>
            <p className="mt-2 text-xs text-slate-500">
              {liveDriver ? "Cross-location live driver" : "Not the live driver"}
            </p>
          </div>

          <div className="data-cell">
            <dt className="data-label">{lastKnown ? "Last-known forecast peak" : "Forecast peak rainfall"}</dt>
            <dd className="data-value">
              {available
                ? formatNumber(weather.forecast_rainfall_intensity_mm_per_hour)
                : "DATA UNAVAILABLE"}
            </dd>
            <p className="mt-2 text-xs text-slate-500">
              {forecastDriver
                ? "Cross-location forecast driver"
                : "Not the forecast driver"}
            </p>
          </div>

          <div className="data-cell">
            <dt className="data-label">Forecast peak time</dt>
            <dd className="data-value text-sm">
              {available ? formatTime(weather.forecast_peak_time) : "DATA UNAVAILABLE"}
            </dd>
          </div>

          <div className="data-cell">
            <dt className="data-label">Last weather update</dt>
            <dd className="data-value text-sm">
              {available ? formatTime(weather.observed_at) : "DATA UNAVAILABLE"}
            </dd>
          </div>
        </dl>

        <div className="mt-4 text-xs text-slate-500">
          Weather source: <span className="font-semibold text-slate-300">{humanizeSource(weather?.source)}</span>
        </div>

        {lastKnown && (
          <div className="mt-3 border-l-2 border-amber-500 bg-amber-950/20 px-3 py-2 text-xs leading-5 text-amber-100">
            LAST KNOWN — NOT LIVE · Captured: {formatTime(freshness?.savedAt)}
          </div>
        )}

        {weather?.failure_code && (
          <div className="mt-4 border-l-2 border-red-500 bg-red-950/25 px-3 py-2 text-xs leading-5 text-red-200">
            Weather provider data is unavailable for this location.
          </div>
        )}
      </div>
    </article>
  );
}