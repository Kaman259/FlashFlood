import { useCallback, useState } from "react";

import { submitEmergencyReport } from "../services/api.js";

export const EMERGENCY_REPORT_STATES = Object.freeze({
  IDLE: "IDLE",
  SUBMITTING: "SUBMITTING",
  SUBMITTED: "SUBMITTED",
  FAILED: "FAILED",
  UNAVAILABLE: "UNAVAILABLE",
});

function readEnabled() {
  return (
    String(import.meta.env.VITE_EMERGENCY_REPORTING_ENABLED ?? "")
      .trim()
      .toLowerCase() === "true"
  );
}

export default function useEmergencyReport() {
  const [status, setStatus] = useState(
    readEnabled()
      ? EMERGENCY_REPORT_STATES.IDLE
      : EMERGENCY_REPORT_STATES.UNAVAILABLE,
  );
  const [error, setError] = useState(null);

  const submit = useCallback(async (payload) => {
    if (status === EMERGENCY_REPORT_STATES.SUBMITTING) {
      return false;
    }

    setStatus(EMERGENCY_REPORT_STATES.SUBMITTING);
    setError(null);

    try {
      const response = await submitEmergencyReport(payload);

      if (response?.status === "received") {
        setStatus(EMERGENCY_REPORT_STATES.SUBMITTED);
        return true;
      }

      setStatus(EMERGENCY_REPORT_STATES.UNAVAILABLE);
      return false;
    } catch {
      setStatus(EMERGENCY_REPORT_STATES.FAILED);
      setError("Report submission failed.");
      return false;
    }
  }, [status]);

  const reset = useCallback(() => {
    setError(null);
    setStatus(
      readEnabled()
        ? EMERGENCY_REPORT_STATES.IDLE
        : EMERGENCY_REPORT_STATES.UNAVAILABLE,
    );
  }, []);

  return {
    status,
    error,
    submit,
    reset,
  };
}