# 0072 — Sentry error tracking

## Status

Accepted

## Context

ADR 0066 (Priority 2, item 4) called for Sentry, explicitly "only after
logging foundations exist" (ADR 0070, done first) and with privacy-conscious
configuration as an explicit requirement — this app handles addresses,
phone numbers, BSNs, and OCR'd legal/personal documents (see the
`personal_data`/`client_profile` document tags), so the generic
Sentry-recommended defaults needed real scrutiny, not a copy-paste.

**Two Sentry projects created** in the `cbrains` org (`collabrains-api`,
`collabrains-web`) via the Sentry MCP, after an initial 403 (the org had
project creation disabled for non-admin members — resolved once the org
owner adjusted permissions).

**Every privacy override was verified against the actual installed SDK,
not assumed from the setup guide** — the guide's own example config uses
options that turned out to be either deprecated or incomplete for what
this app needs:

- **Backend** (`sentry-sdk` 2.66): `send_default_pii=False` (the
  guide's own recommended default is `True` — deliberately overridden),
  `include_local_variables=False` (a traceback in, say, address-parsing
  code could otherwise put a real street address into Sentry as a
  captured local variable), and an `EventScrubber` extending Sentry's
  own `DEFAULT_DENYLIST` with this app's domain-specific sensitive field
  names (`ocr_text`, `address`, `bsn`, `iban`, etc.). Verified with a
  real captured event (fake transport, no network call) that
  `Authorization`/`Cookie` headers come back `[Filtered]` and that stack
  frames carry no `vars` — not assumed from the option names alone.
- **A residual gap found and addressed**: none of the above touches an
  exception's own message *text* — `raise ValueError(f"bad address:
  {addr}")` puts the real address into Sentry regardless of every
  setting above, since scrubbing only acts on known structured field
  *names*, not arbitrary free text. Added a `before_send` hook
  (`_redact_text`) that pattern-matches this app's known sensitive
  shapes (Dutch postal codes, IBANs, phone numbers, BSNs) in the
  exception message and event message text. Documented as best-effort,
  not exhaustive — the real fix for this class of leak is not
  interpolating raw user data into exception messages in application
  code, which this can't guarantee project-wide.
- **Verified the exception handler question directly, not assumed**:
  does Sentry's FastAPI/Starlette integration still capture an exception
  that ADR 0070's catch-all `@app.exception_handler(Exception)` also
  catches? Confirmed with a real test (fake transport, real
  `TestClient` call, a route that raises): yes — Sentry hooks in before
  the registered handler runs, captured envelope shows
  `mechanism.handled: False` even though the client still gets a clean
  500 response.
- **Frontend** (`@sentry/react` 10.67): the setup guide's example uses
  the now-*deprecated* `sendDefaultPii` option — this SDK version's real
  privacy surface is the newer `dataCollection` object (confirmed via
  the installed package's own `.d.ts`, not the guide), configured to
  collect no cookies, no HTTP headers/bodies, no URL query params, and
  no stack-frame variables.
- **Session Replay was in the guide's default recommendation and is
  deliberately NOT enabled** — this app renders legal documents and
  personal data on screen; a session recording is a materially
  different privacy exposure than error/trace metadata, even with text
  masking, and isn't worth it for what was actually asked for (error
  tracking + environment separation).
- **Profiling was not enabled either** — the production host is
  already documented as CPU-constrained (single OpenVZ host,
  `docs/deployment/ai-optimization.md`); continuous profiling overhead
  there is a real cost for a signal that wasn't explicitly requested.

**React version is 18.3.1** (not 19), so `Sentry.ErrorBoundary` wraps the
app in `main.tsx` rather than the newer `reactErrorHandler()` hook
pattern. The fallback UI (`ErrorFallback.tsx`) deliberately avoids
`useTranslation`/design-system components — it's the last-resort render
for when the React tree itself (possibly including i18n/router context)
has crashed, so it only depends on plain global CSS custom properties,
not React context that could itself be part of what broke.

**Router integration**: `apps/web`'s `App.tsx` uses plain
`react-router-dom` v6 `<Routes>`/`<Route>` JSX, not the v6.4+
data-router `createBrowserRouter` API, so
`reactRouterV6BrowserTracingIntegration` is wired via the hooks-based
option (Option C in the setup guide), not `wrapCreateBrowserRouterV6`.

**Both SDKs stay fully inert without a DSN** — `sentry_dsn: str = ""` /
`VITE_SENTRY_DSN` unset means `sentry_sdk.init()`/`Sentry.init()` is never
called at all, so local dev, CI, and tests are entirely unaffected
(verified: the full test suite doesn't need mocking anything Sentry-related,
since it just never initializes).

## Decision

- `services/api/src/api/sentry_config.py`: `init_sentry()`, called from
  `main.py` before `configure_logging()`/`FastAPI()`. New `sentry_dsn`/
  `sentry_environment` settings in `config.py`.
- `apps/web/src/instrument.ts`: `Sentry.init()`, imported first in
  `main.tsx` per the SDK's own requirement. New `ErrorFallback.tsx`
  wrapped via `Sentry.ErrorBoundary`.
- Both DSNs are currently known only to this session and the user (not
  committed anywhere) — enabling this in any real environment means
  setting `SENTRY_DSN`/`SENTRY_ENVIRONMENT` in that environment's real
  `.env`, and `VITE_SENTRY_DSN` in whatever the frontend build process
  reads (e.g. `apps/web/.env.production`, not currently present and not
  created here — no production deploy is happening in this pass).

## Consequences

- Real errors from a running instance (once a DSN is actually configured
  somewhere) are now captured with request correlation (ADR 0070's
  request ID is available as Sentry tags/context via the same
  middleware), without leaking headers, cookies, local variables, or
  (best-effort) known-sensitive text patterns.
- Source map upload for readable production frontend stack traces is
  explicitly out of scope for this pass — it needs a `SENTRY_AUTH_TOKEN`
  and an actual release/build pipeline to upload against, and this
  project's CI (ADR 0068) deliberately doesn't deploy anything yet. Revisit
  once a real deploy pipeline exists.
- Session Replay and Profiling are deliberately not enabled — noted above,
  reconsider only if a concrete need for either appears later.
