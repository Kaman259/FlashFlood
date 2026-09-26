const SCENARIOS = [
  { value: "normal", label: "NORMAL" },
  { value: "watch", label: "WATCH" },
  { value: "moderate-surge", label: "MODERATE SURGE" },
  { value: "critical-surge", label: "CRITICAL SURGE" },
];

export default function DemoScenarioControls({
  selectedScenario,
  loading,
  onChange,
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="section-label">Demonstration controls</p>
          <h2 className="mt-1 text-base font-bold text-slate-100">
            Simulated river scenario
          </h2>
        </div>
        <span className="status-label border-amber-500/50 text-amber-200">
          SIMULATION ONLY
        </span>
      </div>

      <div className="panel-body">
        <p className="max-w-4xl text-sm leading-6 text-slate-400">
          Select a river telemetry scenario. Weather remains unchanged and the
          dashboard requests a fresh result from the backend risk engine.
        </p>

        <div
          className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"
          role="group"
          aria-label="Telemetry demonstration scenario"
        >
          {SCENARIOS.map((scenario) => {
            const active = selectedScenario === scenario.value;

            return (
              <button
                key={scenario.value}
                type="button"
                disabled={loading}
                onClick={() => onChange(scenario.value)}
                aria-pressed={active}
                className={`demo-button ${active ? "demo-button-active" : ""}`}
              >
                <span className="demo-button-state">
                  {active ? "SELECTED" : "SELECT SCENARIO"}
                </span>
                <span className="demo-button-label">{scenario.label}</span>
              </button>
            );
          })}
        </div>

        {loading && (
          <p className="mt-3 text-xs font-semibold uppercase tracking-[0.12em] text-sky-300">
            Updating telemetry and requesting a new backend risk assessment...
          </p>
        )}
      </div>
    </section>
  );
}