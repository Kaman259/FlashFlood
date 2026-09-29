import {
  getApps,
  initializeApp,
} from "firebase/app";
import {
  getMessaging,
  isSupported,
  onRegistered,
  register,
} from "firebase/messaging";

const FIREBASE_APP_NAME = "flashflood-web-fcm";
const REGISTRATION_TIMEOUT_MS = 15000;

function readBoolean(value) {
  return String(value ?? "").trim().toLowerCase() === "true";
}

function readPublicConfig() {
  return {
    apiKey: String(import.meta.env.VITE_FIREBASE_API_KEY ?? "").trim(),
    projectId: String(import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "").trim(),
    messagingSenderId: String(
      import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? "",
    ).trim(),
    appId: String(import.meta.env.VITE_FIREBASE_APP_ID ?? "").trim(),
    vapidKey: String(import.meta.env.VITE_FIREBASE_VAPID_KEY ?? "").trim(),
  };
}

function hasCompletePublicConfig(config) {
  return Boolean(
    config.apiKey &&
      config.projectId &&
      config.messagingSenderId &&
      config.appId &&
      config.vapidKey,
  );
}

export function isFcmFeatureEnabled() {
  return readBoolean(import.meta.env.VITE_FCM_ENABLED);
}

export function hasFcmPublicConfiguration() {
  return hasCompletePublicConfig(readPublicConfig());
}

function getOrInitializeFirebaseApp(config) {
  const existing = getApps().find(
    (app) => app.name === FIREBASE_APP_NAME,
  );

  if (existing) {
    return existing;
  }

  return initializeApp(
    {
      apiKey: config.apiKey,
      projectId: config.projectId,
      messagingSenderId: config.messagingSenderId,
      appId: config.appId,
    },
    FIREBASE_APP_NAME,
  );
}

async function registerMessagingServiceWorker(config) {
  const workerUrl = new URL(
    "/firebase-messaging-sw.js",
    window.location.origin,
  );

  workerUrl.searchParams.set("apiKey", config.apiKey);
  workerUrl.searchParams.set("projectId", config.projectId);
  workerUrl.searchParams.set(
    "messagingSenderId",
    config.messagingSenderId,
  );
  workerUrl.searchParams.set("appId", config.appId);

  const registration = await navigator.serviceWorker.register(
    `${workerUrl.pathname}${workerUrl.search}`,
    {
      scope: "/fcm-messaging/",
    },
  );

  return registration;
}

async function waitForInstallationId(
  messaging,
  options,
) {
  let unsubscribe = null;
  let timeoutId = null;

  const installationPromise = new Promise(
    (resolve, reject) => {
      timeoutId = window.setTimeout(() => {
        reject(new Error("FCM_REGISTRATION_TIMEOUT"));
      }, REGISTRATION_TIMEOUT_MS);

      unsubscribe = onRegistered(
        messaging,
        (installationId) => {
          if (
            typeof installationId !== "string" ||
            installationId.length === 0
          ) {
            reject(new Error("INVALID_INSTALLATION_ID"));
            return;
          }

          resolve(installationId);
        },
      );
    },
  );

  try {
    await register(messaging, options);
    return await installationPromise;
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }

    if (unsubscribe) {
      unsubscribe();
    }
  }
}

export async function requestBrowserAlertRegistration() {
  if (
    !isFcmFeatureEnabled() ||
    !hasFcmPublicConfiguration()
  ) {
    return {
      status: "UNAVAILABLE",
      installationId: null,
    };
  }

  if (
    typeof window === "undefined" ||
    typeof navigator === "undefined" ||
    typeof Notification === "undefined" ||
    !("serviceWorker" in navigator)
  ) {
    return {
      status: "UNAVAILABLE",
      installationId: null,
    };
  }

  let supported = false;

  try {
    supported = await isSupported();
  } catch {
    supported = false;
  }

  if (!supported) {
    return {
      status: "UNAVAILABLE",
      installationId: null,
    };
  }

  let permission = Notification.permission;

  if (permission === "denied") {
    return {
      status: "PERMISSION_DENIED",
      installationId: null,
    };
  }

  if (permission !== "granted") {
    try {
      permission = await Notification.requestPermission();
    } catch {
      return {
        status: "REGISTRATION_FAILED",
        installationId: null,
      };
    }
  }

  if (permission !== "granted") {
    return {
      status: "PERMISSION_DENIED",
      installationId: null,
    };
  }

  const config = readPublicConfig();

  try {
    const firebaseApp = getOrInitializeFirebaseApp(config);
    const messaging = getMessaging(firebaseApp);
    const serviceWorkerRegistration =
      await registerMessagingServiceWorker(config);

    const installationId = await waitForInstallationId(
      messaging,
      {
        vapidKey: config.vapidKey,
        serviceWorkerRegistration,
      },
    );

    return {
      status: "REGISTERED",
      installationId,
    };
  } catch {
    return {
      status: "REGISTRATION_FAILED",
      installationId: null,
    };
  }
}