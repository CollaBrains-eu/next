import * as Sentry from "@sentry/react";
import { useEffect } from "react";
import { createRoutesFromChildren, matchRoutes, useLocation, useNavigationType } from "react-router";

// ADR 0072 (Priority 2, item 4). Must be imported first in main.tsx, before
// any other app code, per Sentry's own setup requirement.
//
// No DSN configured (local dev, CI, or an operator who hasn't set it) means
// Sentry.init is simply never called -- the SDK stays fully inert, same
// pattern as the backend (services/api/src/api/sentry_config.py).
const dsn = import.meta.env.VITE_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    integrations: [
      Sentry.reactRouterBrowserTracingIntegration({
        useEffect,
        useLocation,
        useNavigationType,
        matchRoutes,
        createRoutesFromChildren,
      }),
    ],
    tracesSampleRate: 1.0,
    // Session Replay is deliberately not enabled: this app renders legal
    // documents, addresses, and other personal data (see the "personal_data"/
    // "client_profile" document tags in services/api) on screen -- a session
    // recording is a materially different privacy exposure than error/trace
    // metadata, even with text masking, and isn't worth it for what this app
    // needs from Sentry right now.
    //
    // dataCollection (not the deprecated sendDefaultPii) gives granular
    // control over exactly what gets sent -- verified against the installed
    // SDK's actual type definitions, not just the generic setup guide.
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: { request: false, response: false },
      httpBodies: [],
      urlQueryParams: false,
      // JS equivalent of the backend's include_local_variables=False --
      // don't capture local variable values in stack frames.
      stackFrameVariables: false,
    },
  });
}
