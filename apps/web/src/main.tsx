import "./instrument"; // must be first -- Sentry.init() before any other app code

import * as Sentry from "@sentry/react";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ErrorFallback } from "./components/ErrorFallback";
import { initAnalytics } from "./lib/analytics";
import "./lib/i18n";
import "./index.css";

initAnalytics();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={<ErrorFallback />}>
      <App />
    </Sentry.ErrorBoundary>
  </React.StrictMode>,
);
