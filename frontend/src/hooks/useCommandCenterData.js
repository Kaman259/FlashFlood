import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  loadLastKnown,
  saveLastKnown,
} from "../services/offlineStore.js";

import {
  evaluateRisk,
  fetchHealth,
  fetchLatestTelemetry,
  fetchWeatherSnapshot,
  getApiErrorMessage,
  selectTelemetryScenario,
} from "../services/api.js";

const DEFAULT_REFRESH_INTERVAL_MS = 60000;
const MIN_REFRESH_INTERVAL_MS = 15000;
const VALID_RISK_LEVELS = new Set(["GREEN", "YELLOW", "ORANGE", "RED"]);
const VALID_COVERAGE = new Set(["FULL", "PARTIAL", "UNAVAILABLE"]);

function readRefreshInterval() {
  const configured = Number(import.meta.env.VITE_REFRESH_INTERVAL_MS);

  if (
    Number.isFinite(configured) &&
    configured >= MIN_REFRESH_INTERVAL_MS
  ) {
    return configured;
  }

  return DEFAULT_REFRESH_INTERVAL_MS;
}

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function isValidTelemetry(telemetry) {
  return Boolean(
    telemetry &&
      isFiniteNumber(telemetry.river_level_m) &&
      telemetry.river_level_m >= 0 &&
      isFiniteNumber(telemetry.river_change_m_per_hour) &&
      isFiniteNumber(telemetry.upstream_discharge_m3_per_s) &&
      telemetry.upstream_discharge_m3_per_s >= 0 &&
      typeof telemetry.station_id === "string" &&
      telemetry.station_id.length > 0 &&
      telemetry.station_id.length <= 100,
  );
}

function isValidWeatherSnapshot(weather) {
  if (!weather || !VALID_COVERAGE.has(weather.coverage_status)) {
    return false;
  }

  if (weather.coverage_status !== "FULL") {
    return true;
  }

  return Boolean(
    weather.risk_input_ready === true &&
      isFiniteNumber(
        weather.aggregated_live_rainfall_intensity_mm_per_hour,
      ) &&
      weather.aggregated_live_rainfall_intensity_mm_per_hour >= 0 &&
      isFiniteNumber(
        weather.aggregated_forecast_rainfall_intensity_mm_per_hour,
      ) &&
      weather.aggregated_forecast_rainfall_intensity_mm_per_hour >= 0,
  );
}

function isValidRiskResponse(risk) {
  return Boolean(
    risk &&
      VALID_RISK_LEVELS.has(risk.risk_level) &&
      Number.isInteger(risk.risk_score) &&
      risk.risk_score >= 0 &&
      risk.risk_score <= 100 &&
      Array.isArray(risk.reasons) &&
      risk.reasons.every((reason) => typeof reason === "string") &&
      typeof risk.recommended_action === "string",
  );
}

function formatSavedAt(savedAt) {
  const capturedAt = new Date(savedAt);

  if (Number.isNaN(capturedAt.getTime())) {
    return null;
  }

  return capturedAt.toLocaleString();
}

async function saveValidatedLastKnown(key, data) {
  try {
    await saveLastKnown(key, data);
  } catch {
    // Offline persistence is best-effort and must never break live operation.
  }
}

async function loadValidatedLastKnown(key, validator) {
  try {
    const cached = await loadLastKnown(key);

    if (
      !cached ||
      !validator(cached.data) ||
      !formatSavedAt(cached.savedAt)
    ) {
      return null;
    }

    return cached;
  } catch {
    return null;
  }
}

function lastKnownStatus(label, savedAt) {
  return `LIVE ${label} UNAVAILABLE. LAST KNOWN — NOT LIVE. Captured: ${formatSavedAt(
    savedAt,
  )}.`;
}

function canEvaluateRisk(weather, telemetry) {
  return Boolean(
    isValidTelemetry(telemetry) &&
      isValidWeatherSnapshot(weather) &&
      weather.coverage_status === "FULL" &&
      weather.risk_input_ready === true,
  );
}

function buildRiskRequest(weather, telemetry) {
  if (!canEvaluateRisk(weather, telemetry)) {
    return null;
  }

  return {
    live_rainfall_intensity_mm_per_hour:
      weather.aggregated_live_rainfall_intensity_mm_per_hour,
    forecast_rainfall_intensity_mm_per_hour:
      weather.aggregated_forecast_rainfall_intensity_mm_per_hour,
    river_level_m: telemetry.river_level_m,
    river_change_m_per_hour: telemetry.river_change_m_per_hour,
    upstream_discharge_m3_per_s: telemetry.upstream_discharge_m3_per_s,
    station_id: telemetry.station_id,
  };
}

function getRiskUnavailableReason(weather, telemetry, riskError) {
  if (riskError) {
    return riskError;
  }

  if (!telemetry) {
    return "Telemetry is unavailable, so risk cannot be evaluated.";
  }

  if (!isValidTelemetry(telemetry)) {
    return "Telemetry data is invalid, so risk evaluation is paused.";
  }

  if (!weather) {
    return "Weather data is unavailable, so risk cannot be evaluated.";
  }

  if (!isValidWeatherSnapshot(weather)) {
    return "Weather data is invalid, so risk evaluation is paused.";
  }

  if (
    weather.coverage_status !== "FULL" ||
    weather.risk_input_ready !== true
  ) {
    return "Full weather coverage is required before the backend risk engine can evaluate risk.";
  }

  return null;
}

export function useCommandCenterData() {
  const [weather, setWeather] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [risk, setRisk] = useState(null);

  const [browserOnline, setBrowserOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );
  const [backendStatus, setBackendStatus] = useState("CHECKING");
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState("normal");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [riskAssessedAt, setRiskAssessedAt] = useState(null);

  const [errors, setErrors] = useState({
    weather: null,
    telemetry: null,
    risk: null,
  });

  const [freshness, setFreshness] = useState({
    weather: { mode: "UNAVAILABLE", savedAt: null },
    telemetry: { mode: "UNAVAILABLE", savedAt: null },
    risk: { mode: "UNAVAILABLE", savedAt: null },
  });

  const setFreshnessEntry = useCallback((key, mode, savedAt = null) => {
    setFreshness((current) => ({
      ...current,
      [key]: { mode, savedAt },
    }));
  }, []);

  const operatingMode = useMemo(() => {
    if (!browserOnline) {
      return "OFFLINE";
    }

    if (backendStatus === "CHECKING") {
      return "CHECKING";
    }

    const allRequiredDataLive =
      freshness.weather.mode === "LIVE" &&
      freshness.telemetry.mode === "LIVE" &&
      freshness.risk.mode === "LIVE";

    if (backendStatus === "ONLINE" && allRequiredDataLive) {
      return "FULL_ONLINE";
    }

    return "DEGRADED";
  }, [browserOnline, backendStatus, freshness]);

  const refreshIntervalMs = useMemo(readRefreshInterval, []);
  const refreshInFlight = useRef(false);
  const weatherLiveRef = useRef(false);
  const telemetryLiveRef = useRef(false);

  const loadCachedRiskForDisplay = useCallback(async (fallbackMessage) => {
    const cached = await loadValidatedLastKnown(
      "risk",
      isValidRiskResponse,
    );

    if (cached) {
      setRisk(cached.data);
      setRiskAssessedAt(new Date(cached.savedAt));
      setFreshnessEntry("risk", "LAST_KNOWN", cached.savedAt);
      setErrors((current) => ({
        ...current,
        risk: lastKnownStatus("RISK ASSESSMENT", cached.savedAt),
      }));
      return cached.data;
    }

    setRisk(null);
    setRiskAssessedAt(null);
    setFreshnessEntry("risk", "UNAVAILABLE");
    setErrors((current) => ({
      ...current,
      risk: fallbackMessage,
    }));
    return null;
  }, [setFreshnessEntry]);

  const evaluateWithData = useCallback(
    async (nextWeather, nextTelemetry) => {
      const payload = buildRiskRequest(nextWeather, nextTelemetry);

      if (!payload) {
        return loadCachedRiskForDisplay(
          "Current live inputs are insufficient for a new risk assessment.",
        );
      }

      try {
        const result = await evaluateRisk(payload);

        if (!isValidRiskResponse(result)) {
          return loadCachedRiskForDisplay(
            "The backend returned an invalid risk response.",
          );
        }

        const assessedAt = new Date();

        setRisk(result);
        setRiskAssessedAt(assessedAt);
        setFreshnessEntry("risk", "LIVE");
        setErrors((current) => ({ ...current, risk: null }));

        await saveValidatedLastKnown("risk", result);

        return result;
      } catch (error) {
        const message = getApiErrorMessage(
          error,
          "Risk evaluation failed.",
        );

        return loadCachedRiskForDisplay(message);
      }
    },
    [loadCachedRiskForDisplay, setFreshnessEntry],
  );

  const refresh = useCallback(
    async ({ initial = false } = {}) => {
      if (refreshInFlight.current) {
        return;
      }

      refreshInFlight.current = true;

      if (initial) {
        setInitialLoading(true);
      } else {
        setRefreshing(true);
      }

      try {
        const [healthResult, weatherResult, telemetryResult] =
          await Promise.allSettled([
            fetchHealth(),
            fetchWeatherSnapshot(),
            fetchLatestTelemetry(),
          ]);

        let nextWeather = null;
        let nextTelemetry = null;

        setBackendStatus(
          healthResult.status === "fulfilled" ? "ONLINE" : "OFFLINE",
        );

        if (
          weatherResult.status === "fulfilled" &&
          isValidWeatherSnapshot(weatherResult.value)
        ) {
          nextWeather = weatherResult.value;
          weatherLiveRef.current = true;
          setFreshnessEntry("weather", "LIVE");

          setWeather(nextWeather);
          setErrors((current) => ({ ...current, weather: null }));

          await saveValidatedLastKnown("weather", nextWeather);
        } else {
          weatherLiveRef.current = false;

          const cachedWeather = await loadValidatedLastKnown(
            "weather",
            isValidWeatherSnapshot,
          );

          if (cachedWeather) {
            setWeather(cachedWeather.data);
            setFreshnessEntry(
              "weather",
              "LAST_KNOWN",
              cachedWeather.savedAt,
            );
            setErrors((current) => ({
              ...current,
              weather: lastKnownStatus(
                "WEATHER",
                cachedWeather.savedAt,
              ),
            }));
          } else {
            setWeather(null);
            setFreshnessEntry("weather", "UNAVAILABLE");
            setErrors((current) => ({
              ...current,
              weather:
                weatherResult.status === "fulfilled"
                  ? "The backend returned invalid weather data."
                  : getApiErrorMessage(
                      weatherResult.reason,
                      "Weather request failed.",
                    ),
            }));
          }
        }

        if (
          telemetryResult.status === "fulfilled" &&
          isValidTelemetry(telemetryResult.value)
        ) {
          nextTelemetry = telemetryResult.value;
          telemetryLiveRef.current = true;
          setFreshnessEntry("telemetry", "LIVE");

          setTelemetry(nextTelemetry);
          setSelectedScenario(nextTelemetry.scenario ?? "normal");
          setErrors((current) => ({ ...current, telemetry: null }));

          await saveValidatedLastKnown(
            "telemetry",
            nextTelemetry,
          );
        } else {
          telemetryLiveRef.current = false;

          const cachedTelemetry = await loadValidatedLastKnown(
            "telemetry",
            isValidTelemetry,
          );

          if (cachedTelemetry) {
            setTelemetry(cachedTelemetry.data);
            setFreshnessEntry(
              "telemetry",
              "LAST_KNOWN",
              cachedTelemetry.savedAt,
            );

            if (cachedTelemetry.data.scenario) {
              setSelectedScenario(cachedTelemetry.data.scenario);
            }

            setErrors((current) => ({
              ...current,
              telemetry: lastKnownStatus(
                "TELEMETRY",
                cachedTelemetry.savedAt,
              ),
            }));
          } else {
            setTelemetry(null);
            setFreshnessEntry("telemetry", "UNAVAILABLE");
            setErrors((current) => ({
              ...current,
              telemetry:
                telemetryResult.status === "fulfilled"
                  ? "The backend returned invalid telemetry data."
                  : getApiErrorMessage(
                      telemetryResult.reason,
                      "Telemetry request failed.",
                    ),
            }));
          }
        }

        // Only current successful API responses are eligible to create a new
        // authoritative risk assessment. Cached weather/telemetry are display-only.
        await evaluateWithData(nextWeather, nextTelemetry);
        setLastUpdated(new Date());
      } finally {
        refreshInFlight.current = false;
        setInitialLoading(false);
        setRefreshing(false);
      }
    },
    [evaluateWithData, setFreshnessEntry],
  );

  const changeScenario = useCallback(
    async (scenario) => {
      const previousScenario = telemetry?.scenario ?? selectedScenario;

      setScenarioLoading(true);

      try {
        const nextTelemetry = await selectTelemetryScenario(scenario);

        if (!isValidTelemetry(nextTelemetry)) {
          throw new Error("INVALID_TELEMETRY_RESPONSE");
        }

        telemetryLiveRef.current = true;
        setFreshnessEntry("telemetry", "LIVE");

        setTelemetry(nextTelemetry);
        setSelectedScenario(nextTelemetry.scenario ?? scenario);
        setErrors((current) => ({ ...current, telemetry: null }));

        await saveValidatedLastKnown(
          "telemetry",
          nextTelemetry,
        );

        await evaluateWithData(
          weatherLiveRef.current ? weather : null,
          nextTelemetry,
        );
        setLastUpdated(new Date());
      } catch (error) {
        setSelectedScenario(previousScenario);
        setErrors((current) => ({
          ...current,
          telemetry:
            error?.message === "INVALID_TELEMETRY_RESPONSE"
              ? "The backend returned invalid telemetry data."
              : getApiErrorMessage(
                  error,
                  "Could not change the telemetry demo scenario.",
                ),
        }));
      } finally {
        setScenarioLoading(false);
      }
    },
    [
      evaluateWithData,
      selectedScenario,
      telemetry?.scenario,
      weather,
      setFreshnessEntry,
    ],
  );

  useEffect(() => {
    const handleOnline = () => {
      setBrowserOnline(true);

      // Browser connectivity alone does not prove backend availability.
      // Reuse the existing refresh path to verify backend/live-feed state.
      refresh();
    };

    const handleOffline = () => {
      setBrowserOnline(false);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [refresh]);

  useEffect(() => {
    refresh({ initial: true });

    const intervalId = window.setInterval(() => {
      refresh();
    }, refreshIntervalMs);

    return () => window.clearInterval(intervalId);
  }, [refresh, refreshIntervalMs]);

  return {
    weather,
    telemetry,
    risk,
    browserOnline,
    backendStatus,
    operatingMode,
    initialLoading,
    refreshing,
    scenarioLoading,
    selectedScenario,
    lastUpdated,
    riskAssessedAt,
    errors,
    freshness,
    refreshIntervalMs,
    riskUnavailableReason: getRiskUnavailableReason(
      weather,
      telemetry,
      errors.risk,
    ),
    refresh,
    changeScenario,
  };
}