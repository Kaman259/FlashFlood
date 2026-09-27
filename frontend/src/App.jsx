import DemoScenarioControls from "./components/dashboard/DemoScenarioControls.jsx";
import StudyAreaMap from "./components/map/StudyAreaMap.jsx";
import LocationStatus from "./components/location/LocationStatus.jsx";
import NotificationStatus from "./components/notifications/NotificationStatus.jsx";
import SmsFallbackStatus from "./components/communications/SmsFallbackStatus.jsx";
import EmergencyReportPanel from "./components/communications/EmergencyReportPanel.jsx";
import RiskStatusCard from "./components/dashboard/RiskStatusCard.jsx";
import RiverTelemetryCard from "./components/dashboard/RiverTelemetryCard.jsx";
import SystemStatus from "./components/dashboard/SystemStatus.jsx";
import WeatherCard from "./components/dashboard/WeatherCard.jsx";
import { useCommandCenterData } from "./hooks/useCommandCenterData.js";

function Header({ backendStatus, refreshing, onRefresh, lastUpdated }) {
  const online = backendStatus === "ONLINE";

  return (
    <header className="border-b border-slate-700 bg-[#0a111a]">
      <div className="mx-auto max-w-[1500px] px-4 lg:px-6">
        <div className="grid gap-3 py-4 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex items-center gap-3">
              <div className="h-5 w-1 bg-sky-400" aria-hidden="true" />
              <h1 className="text-xl font-black tracking-[-0.02em] text-white">
                FlashFlood Command Center
              </h1>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Hyperlocal Early-Warning &amp; Resilient Evacuation Support System
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`status-label ${
                online
                  ? "border-emerald-600/60 text-emerald-200"
                  : backendStatus === "OFFLINE"
                    ? "border-red-600/60 text-red-200"
                    : "text-slate-300"
              }`}
            >
              Backend: {backendStatus}
            </span>

            <button
              type="button"
              onClick={() => onRefresh()}
              disabled={refreshing}
              className="command-button"
            >
              {refreshing ? "Refreshing..." : "Refresh data"}
            </button>
          </div>
        </div>

        <div className="grid gap-x-6 gap-y-2 border-t border-slate-800 py-2 text-[11px] uppercase tracking-[0.08em] text-slate-500 sm:grid-cols-2 xl:grid-cols-4">
          <span>
            Study area: <strong className="text-slate-300">Sonari / Charaideo, Assam</strong>
          </span>
          <span>
            Upstream: <strong className="text-slate-300">Mokokchung, Nagaland</strong>
          </span>
          <span>
            Last refresh: {lastUpdated ? lastUpdated.toLocaleTimeString() : "waiting"}
          </span>
          <span>Risk authority: Backend engine</span>
        </div>
      </div>
    </header>
  );
}

function ErrorBanner({ errors }) {
  const messages = [errors.weather, errors.telemetry, errors.risk].filter(Boolean);

  if (!messages.length) {
    return null;
  }

  return (
    <div
      role="alert"
      className="border-l-4 border-red-500 bg-red-950/25 px-4 py-3 text-sm text-red-100"
    >
      <p className="font-bold">DATA FEED ALERT</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-red-200">
        {messages.map((message, index) => (
          <li key={`${message}-${index}`}>{message}</li>
        ))}
      </ul>
    </div>
  );
}

function CoverageBanner({ weather }) {
  if (weather?.coverage_status === "PARTIAL") {
    return (
      <div
        role="status"
        className="border-l-4 border-yellow-300 bg-yellow-950/20 px-4 py-3 text-sm leading-6 text-yellow-100"
      >
        <strong>PARTIAL WEATHER COVERAGE.</strong> Available location data is
        shown, but automated risk evaluation is paused until both weather
        locations are available.
      </div>
    );
  }

  if (weather?.coverage_status === "UNAVAILABLE") {
    return (
      <div
        role="alert"
        className="border-l-4 border-red-500 bg-red-950/25 px-4 py-3 text-sm leading-6 text-red-100"
      >
        <strong>WEATHER DATA UNAVAILABLE.</strong> Missing rainfall is not
        represented as zero. Automated risk evaluation is paused.
      </div>
    );
  }

  return null;
}

function App() {
  const {
    weather,
    telemetry,
    risk,
    backendStatus,
    initialLoading,
    refreshing,
    scenarioLoading,
    selectedScenario,
    lastUpdated,
    riskAssessedAt,
    errors,
    freshness,
    refreshIntervalMs,
    riskUnavailableReason,
    refresh,
    changeScenario,
  } = useCommandCenterData();

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <Header
        backendStatus={backendStatus}
        refreshing={refreshing}
        onRefresh={refresh}
        lastUpdated={lastUpdated}
      />

      <main className="mx-auto max-w-[1500px] space-y-4 px-4 py-4 lg:px-6 lg:py-5">
        <ErrorBanner errors={errors} />
        <CoverageBanner weather={weather} />

        <RiskStatusCard
          risk={risk}
          weather={weather}
          telemetry={telemetry}
          assessmentTimestamp={riskAssessedAt}
          loading={initialLoading}
          unavailableReason={riskUnavailableReason}
          freshness={freshness}
        />

        <StudyAreaMap />

        <LocationStatus />

        <NotificationStatus />

        <section className="grid gap-4 lg:grid-cols-2">
          <SmsFallbackStatus />
          <EmergencyReportPanel />
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <WeatherCard
            title="Upstream weather"
            subtitle="Mokokchung, Nagaland"
            weather={weather?.upstream}
            role="UPSTREAM"
            liveDrivers={weather?.live_driver_locations ?? []}
            forecastDrivers={weather?.forecast_driver_locations ?? []}
            freshness={freshness.weather}
          />
          <WeatherCard
            title="Downstream weather"
            subtitle="Sonari / Charaideo, Assam"
            weather={weather?.downstream}
            role="DOWNSTREAM"
            liveDrivers={weather?.live_driver_locations ?? []}
            forecastDrivers={weather?.forecast_driver_locations ?? []}
            freshness={freshness.weather}
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <RiverTelemetryCard
            telemetry={telemetry}
            error={errors.telemetry}
            freshness={freshness.telemetry}
          />
          <SystemStatus
            backendStatus={backendStatus}
            weather={weather}
            telemetry={telemetry}
            risk={risk}
            assessmentTimestamp={riskAssessedAt}
            lastUpdated={lastUpdated}
            refreshIntervalMs={refreshIntervalMs}
          />
        </section>

        <DemoScenarioControls
          selectedScenario={selectedScenario}
          loading={scenarioLoading || initialLoading || refreshing}
          onChange={changeScenario}
        />

        <footer className="border-t border-slate-800 py-4 text-xs leading-5 text-slate-500">
          Prototype monitoring interface. Weather is normalized by the backend
          weather service. River telemetry is simulated demonstration data.
          Warning outputs are generated by the backend risk engine and are not
          operational emergency guidance.
        </footer>
      </main>
    </div>
  );
}

export default App;