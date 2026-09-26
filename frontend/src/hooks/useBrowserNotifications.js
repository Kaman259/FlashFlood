import { useCallback, useState } from "react";

import {
  hasFcmPublicConfiguration,
  isFcmFeatureEnabled,
  requestBrowserAlertRegistration,
} from "../services/firebaseMessaging.js";
import { registerNotificationInstallation } from "../services/api.js";

export const NOTIFICATION_STATES = Object.freeze({
  NOT_ENABLED: "NOT_ENABLED",
  REQUESTING_PERMISSION: "REQUESTING_PERMISSION",
  ENABLED: "ENABLED",
  PERMISSION_DENIED: "PERMISSION_DENIED",
  UNAVAILABLE: "UNAVAILABLE",
  REGISTRATION_FAILED: "REGISTRATION_FAILED",
});

function initialStatus() {
  return (
    isFcmFeatureEnabled() &&
    hasFcmPublicConfiguration()
  )
    ? NOTIFICATION_STATES.NOT_ENABLED
    : NOTIFICATION_STATES.UNAVAILABLE;
}

export default function useBrowserNotifications() {
  const [status, setStatus] = useState(initialStatus);

  const enableAlerts = useCallback(async () => {
    setStatus(NOTIFICATION_STATES.REQUESTING_PERMISSION);

    let browserRegistration;

    try {
      browserRegistration =
        await requestBrowserAlertRegistration();
    } catch {
      setStatus(
        NOTIFICATION_STATES.REGISTRATION_FAILED,
      );
      return;
    }

    if (
      browserRegistration.status === "PERMISSION_DENIED"
    ) {
      setStatus(
        NOTIFICATION_STATES.PERMISSION_DENIED,
      );
      return;
    }

    if (browserRegistration.status === "UNAVAILABLE") {
      setStatus(NOTIFICATION_STATES.UNAVAILABLE);
      return;
    }

    if (
      browserRegistration.status !== "REGISTERED" ||
      !browserRegistration.installationId
    ) {
      setStatus(
        NOTIFICATION_STATES.REGISTRATION_FAILED,
      );
      return;
    }

    try {
      const response =
        await registerNotificationInstallation(
          browserRegistration.installationId,
          true,
        );

      if (response?.status === "registered") {
        setStatus(NOTIFICATION_STATES.ENABLED);
      } else if (response?.status === "unavailable") {
        setStatus(NOTIFICATION_STATES.UNAVAILABLE);
      } else {
        setStatus(
          NOTIFICATION_STATES.REGISTRATION_FAILED,
        );
      }
    } catch {
      setStatus(
        NOTIFICATION_STATES.REGISTRATION_FAILED,
      );
    }
  }, []);

  return {
    status,
    enableAlerts,
  };
}