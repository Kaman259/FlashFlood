import WarningReasons from "./WarningReasons.jsx";

const RISK_STYLES = {
  GREEN: {
    descriptor: "NORMAL",
    border: "border-l-emerald-400",
    text: "text-emerald-300",
    label: "border-emerald-500/60 bg-emerald-950/40 text-emerald-200",
  },
  YELLOW: {
    descriptor: "WATCH",
    border: "border-l-yellow-300",
    text: "text-yellow-200",
    label: "border-yellow-400/60 bg-yellow-950/35 text-yellow-100",
  },
  ORANGE: {
    descriptor: "WARNING",
    border: "border-l-orange-400",
    text: "text-orange-300",
    label: "border-orange-500/60 bg-orange-950/35 text-orange-100",
  },
  RED: {
    descriptor: "DANGER",
    border: "border-l-red-500",
    text: "text-red-300",
    label: "border-red-500/60 bg-red-950/40 text-red-100",
  },
};

function formatTimestamp(value) {
  if (!value) {
    return "DATA UNAVAILABLE";
  }

  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "DATA UNAVAILABLE";
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function formatNumber(value, suffix) {
  if (value == null || !Number.isFinite(Number(value))) {
    return "DATA UNAVAILABLE";
  }

  return `${Number(value).toFixed(2)} ${suffix}`;
}

function AssessmentInputs({ weather, telemetry }) {
  const weatherReady =
    weather?.coverage_status === "FULL" && weather?.risk_input_ready === true;

  return (
    <div>
      <p className="section-label">Assessment inputs</p>
      <dl className="mt-3 data-grid sm:grid-cols-2 xl:grid-cols-5">
        <div className="data-cell">
          <dt className="data-label">Live rainfall</dt>
          <dd className="data-value">
            {weatherReady
              ? formatNumber(
                  weather.aggregated_live_rainfall_intensity_mm_per_hour,
                  "mm/hour",
                )
              : "DATA UNAVAILABLE"}
          </dd>
        </div>

        <div className="data-cell">
          <dt className="data-label">Forecast rainfall</dt>
          <dd className="data-value">
            {weatherReady
              ? formatNumber(
                  weather.aggregated_forecast_rainfall_intensity_mm_per_hour,
                  "mm/hour",
                )
              : "DATA UNAVAILABLE"}
          </dd>
        </div>

        <div className="data-cell">
          <dt className="data-label">River level</dt>
          <dd className="data-value">
            {formatNumber(telemetry?.river_level_m, "m")}
          </dd>
        </div>

        <div className="data-cell">
          <dt className="data-label">River change</dt>
          <dd className="data-value">
            {formatNumber(telemetry?.river_change_m_per_hour, "m/hour")}
          </dd>
        </div>

        <div className="data-cell">
          <dt className="data-label">Upstream discharge</dt>
          <dd className="data-value">
            {formatNumber(telemetry?.upstream_discharge_m3_per_s, "m3/s")}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export default function RiskStatusCard({
  risk,
  weather,
  telemetry,
  assessmentTimestamp,
  loading,
  unavailableReason,
}) {
  if (loading) {
    return (
      <section className="panel" aria-busy="true">
        <div className="panel-header">
          <p className="section-label">Current risk</p>
          <span className="status-label text-slate-300">LOADING</span>
        </div>
        <div className="panel-body">
          <p className="text-sm text-slate-400">
            Waiting for weather, telemetry, and backend evaluation.
          </p>
        </div>
      </section>
    );
  }

  if (!risk || !RISK_STYLES[risk.risk_level]) {
    return (
      <section className="panel border-l-4 border-l-slate-500">
        <div className="panel-header">
          <p className="section-label">Current risk</p>
          <span className="status-label text-slate-300">NO RESULT</span>
        </div>
        <div className="panel-body space-y-5">
          <div>
            <p className="text-3xl font-black tracking-tight text-slate-200">
              DATA UNAVAILABLE
            </p>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
              {unavailableReason ||
                "The backend has not returned a valid risk assessment."}
            </p>
          </div>

          <AssessmentInputs weather={weather} telemetry={telemetry} />
          <WarningReasons risk={null} unavailableReason={unavailableReason} />
        </div>
      </section>
    );
  }

  const style = RISK_STYLES[risk.risk_level];

  return (
    <section className={`panel border-l-4 ${style.border}`}>
      <div className="panel-header">
        <p className="section-label">Current risk</p>
        <span className={`status-label ${style.label}`}>BACKEND ASSESSMENT</span>
      </div>

      <div className="panel-body space-y-5">
        <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <p className={`text-4xl font-black tracking-[-0.035em] ${style.text}`}>
              {risk.risk_level} - {style.descriptor}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
              <span>Authority: Backend risk engine</span>
              <span>Assessment received: {formatTimestamp(assessmentTimestamp)}</span>
            </div>
          </div>

          <div className="border-l border-slate-700 pl-5 lg:min-w-40">
            <p className="data-label">Risk score</p>
            <p className="mt-1 text-3xl font-black text-white">
              {risk.risk_score}
              <span className="ml-1 text-sm font-semibold text-slate-500">
                / 99
              </span>
            </p>
          </div>
        </div>

        <AssessmentInputs weather={weather} telemetry={telemetry} />
        <WarningReasons risk={risk} unavailableReason={unavailableReason} />
      </div>
    </section>
  );
}