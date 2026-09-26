import { useCallback, useState } from "react";

import { PROTOTYPE_AFFECTED_AREA } from "../components/map/studyAreaData.js";
import { isPointInPolygon } from "../utils/pointInPolygon.js";

export const LOCATION_STATES = Object.freeze({
  NOT_CHECKED: "NOT_CHECKED",
  CHECKING: "CHECKING",
  INSIDE_AFFECTED_AREA: "INSIDE_AFFECTED_AREA",
  OUTSIDE_AFFECTED_AREA: "OUTSIDE_AFFECTED_AREA",
  PERMISSION_DENIED: "PERMISSION_DENIED",
  POSITION_UNAVAILABLE: "POSITION_UNAVAILABLE",
  REQUEST_TIMEOUT: "REQUEST_TIMEOUT",
  GEOLOCATION_UNSUPPORTED: "GEOLOCATION_UNSUPPORTED",
});

const GEOLOCATION_OPTIONS = Object.freeze({
  enableHighAccuracy: false,
  timeout: 10000,
  maximumAge: 0,
});

function isValidBrowserCoordinate(latitude, longitude) {
  return (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
  );
}

function mapGeolocationError(error) {
  switch (error?.code) {
    case 1:
      return LOCATION_STATES.PERMISSION_DENIED;
    case 2:
      return LOCATION_STATES.POSITION_UNAVAILABLE;
    case 3:
      return LOCATION_STATES.REQUEST_TIMEOUT;
    default:
      return LOCATION_STATES.POSITION_UNAVAILABLE;
  }
}

export default function useBrowserLocation() {
  const [status, setStatus] = useState(LOCATION_STATES.NOT_CHECKED);

  const checkLocation = useCallback(() => {
    if (
      typeof navigator === "undefined" ||
      !("geolocation" in navigator)
    ) {
      setStatus(LOCATION_STATES.GEOLOCATION_UNSUPPORTED);
      return;
    }

    setStatus(LOCATION_STATES.CHECKING);

    try {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const latitude = position?.coords?.latitude;
          const longitude = position?.coords?.longitude;

          if (!isValidBrowserCoordinate(latitude, longitude)) {
            setStatus(LOCATION_STATES.POSITION_UNAVAILABLE);
            return;
          }

          const insideAffectedArea = isPointInPolygon(
            latitude,
            longitude,
            PROTOTYPE_AFFECTED_AREA.positions,
          );

          setStatus(
            insideAffectedArea
              ? LOCATION_STATES.INSIDE_AFFECTED_AREA
              : LOCATION_STATES.OUTSIDE_AFFECTED_AREA,
          );
        },
        (error) => {
          setStatus(mapGeolocationError(error));
        },
        GEOLOCATION_OPTIONS,
      );
    } catch {
      setStatus(LOCATION_STATES.POSITION_UNAVAILABLE);
    }
  }, []);

  return {
    status,
    checking: status === LOCATION_STATES.CHECKING,
    checkLocation,
  };
}