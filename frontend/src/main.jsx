import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(<App />);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        console.log(
          "FlashFlood Service Worker registered:",
          registration.scope
        );
      })
      .catch((error) => {
        console.error(
          "FlashFlood Service Worker registration failed:",
          error
        );
      });
  });
}