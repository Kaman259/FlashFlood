import axios from "axios";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const ALLOWED_SCENARIOS = new Set([
  "normal",
  "watch",
  "moderate-surge",
  "critical-surge",
]);

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 12000,
  withCredentials: false,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

export async function fetchHealth() {
  const response = await apiClient.get("/api/health");
  return response.data;
}

export async function fetchLatestTelemetry() {
  const response = await apiClient.get("/api/telemetry/latest");
  return response.data;
}

export async function selectTelemetryScenario(scenario) {
  if (!ALLOWED_SCENARIOS.has(scenario)) {
    throw new Error("INVALID_DEMO_SCENARIO");
  }

  const response = await apiClient.get(
    `/api/telemetry/demo/${encodeURIComponent(scenario)}`,
  );
  return response.data;
}

export async function fetchWeatherSnapshot() {
  try {
    const response = await apiClient.get("/api/weather");
    return response.data;
  } catch (error) {
    if (
      error.response?.status === 503 &&
      error.response?.data?.coverage_status === "UNAVAILABLE"
    ) {
      return error.response.data;
    }

    throw error;
  }
}

export async function evaluateRisk(payload) {
  const response = await apiClient.post("/api/risk/evaluate", payload);
  return response.data;
}

export async function registerNotificationInstallation(
  installationId,
  enabled = true,
) {
  if (
    typeof installationId !== "string" ||
    installationId.length === 0
  ) {
    throw new Error("INVALID_NOTIFICATION_INSTALLATION");
  }

  const response = await apiClient.post(
    "/api/notifications/registration",
    {
      installation_id: installationId,
      enabled: Boolean(enabled),
    },
  );

  return response.data;
}

export function getApiErrorMessage(error, fallbackMessage) {
  if (error?.message === "INVALID_DEMO_SCENARIO") {
    return "Invalid demonstration scenario.";
  }

  if (error?.code === "ECONNABORTED") {
    return "Request timed out.";
  }

  if (!error?.response) {
    return "Backend connection unavailable.";
  }

  const status = error.response.status;

  if (status === 400 || status === 422) {
    return "The backend rejected invalid request data.";
  }

  if (status === 401 || status === 403) {
    return "This operation is not authorized.";
  }

  if (status >= 500) {
    return "A backend service error prevented this request from completing.";
  }

  return fallbackMessage;
}

export { API_BASE_URL };