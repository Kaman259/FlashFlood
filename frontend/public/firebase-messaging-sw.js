/*
 * Stage 11 FCM-only service worker.
 * This intentionally does not implement Cache API, offline data, background
 * sync, map caching, risk calculations, or browser location access.
 *
 * Firebase Web configuration is public application configuration. The values
 * are supplied in the service-worker registration URL by the React app.
 */

importScripts(
  "https://www.gstatic.com/firebasejs/12.19.0/firebase-app-compat.js",
);
importScripts(
  "https://www.gstatic.com/firebasejs/12.19.0/firebase-messaging-compat.js",
);

const params = new URL(self.location.href).searchParams;

const firebaseConfig = {
  apiKey: params.get("apiKey") || "",
  projectId: params.get("projectId") || "",
  messagingSenderId: params.get("messagingSenderId") || "",
  appId: params.get("appId") || "",
};

const configured = Object.values(firebaseConfig).every(
  (value) => typeof value === "string" && value.length > 0,
);

if (configured) {
  firebase.initializeApp(firebaseConfig);

  // Initializing Messaging installs the FCM background message handling.
  // Notification payload display is left to FCM to avoid duplicate alerts.
  firebase.messaging();
}