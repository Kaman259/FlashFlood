import { useState } from "react";

import useEmergencyReport, {
  EMERGENCY_REPORT_STATES,
} from "../../hooks/useEmergencyReport.js";

const CATEGORIES = [
  "FLOODING",
  "TRAPPED",
  "MEDICAL",
  "EVACUATION_HELP",
  "INFRASTRUCTURE_DAMAGE",
  "OTHER",
];

export default function EmergencyReportPanel() {
  const [category, setCategory] = useState("FLOODING");
  const [message, setMessage] = useState("");
  const { status, error, submit, reset } = useEmergencyReport();

  const submitting =
    status === EMERGENCY_REPORT_STATES.SUBMITTING;
  const unavailable =
    status === EMERGENCY_REPORT_STATES.UNAVAILABLE;

  async function handleSubmit(event) {
    event.preventDefault();

    const accepted = await submit({
      category,
      message,
    });

    if (accepted) {
      setMessage("");
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="section-label">EMERGENCY REPORTING</p>
          <p className="mt-1 text-[11px] font-bold text-slate-300">
            Prototype only — this does not contact emergency services.
          </p>
        </div>
      </div>

      <form className="panel-body space-y-3" onSubmit={handleSubmit}>
        <p className="text-xs leading-5 text-slate-400">
          Do not include phone numbers, exact addresses, or precise location.
          Prototype submission only.
        </p>

        <label className="communication-field">
          <span>Category</span>
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            disabled={submitting || unavailable}
          >
            {CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>

        <label className="communication-field">
          <span>Message</span>
          <textarea
            rows="4"
            minLength="5"
            maxLength="500"
            value={message}
            onChange={(event) => {
              if (
                status === EMERGENCY_REPORT_STATES.SUBMITTED ||
                status === EMERGENCY_REPORT_STATES.FAILED
              ) {
                reset();
              }
              setMessage(event.target.value);
            }}
            disabled={submitting || unavailable}
            required
          />
        </label>

        {unavailable ? (
          <p className="status-label text-slate-300">
            REPORTING UNAVAILABLE
          </p>
        ) : status === EMERGENCY_REPORT_STATES.SUBMITTED ? (
          <p className="status-label border-emerald-700/60 text-emerald-200">
            REPORT RECEIVED
          </p>
        ) : error ? (
          <p className="text-xs text-red-200">{error}</p>
        ) : null}

        <button
          type="submit"
          className="command-button"
          disabled={
            submitting ||
            unavailable ||
            message.trim().length < 5
          }
        >
          {submitting ? "SUBMITTING..." : "SUBMIT REPORT"}
        </button>
      </form>
    </section>
  );
}