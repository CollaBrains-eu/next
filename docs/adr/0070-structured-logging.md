# 0070 — Structured logging and request correlation

## Status

Accepted

## Context

ADR 0066 (Priority 2, item 3) found `services/api` had ~19 modules calling
`logging.getLogger(__name__)` but nothing ever called `logging.basicConfig`
— those log lines had no configured formatter, no destination guarantee
beyond whatever uvicorn's own default did, and no way to correlate every
line a single request produced. No request-ID/correlation-ID existed
anywhere.

**Stdlib-only, deliberately** — a correct JSON formatter with a
per-request correlation ID is roughly 60 lines
(`services/api/src/api/logging_config.py`): a `logging.Filter` that reads a
`contextvars.ContextVar` and stamps it onto every `LogRecord`, and a
`logging.Formatter` subclass that serializes the record (plus anything
passed via `extra={...}`) to one JSON line. Not worth a new dependency
(e.g. `structlog`) for what this project needs today.

**Request ID via `contextvars`, not by threading it through every function
signature** — a `@app.middleware("http")` wrapper generates (or honors an
incoming `X-Request-ID` header, in case a future upstream hop sets one)
a UUID once per request, sets it in the ContextVar, and resets it when the
request finishes. Any `logger.info(...)` call anywhere in the call stack —
a router, a service function, a background task spawned from the request —
picks up the same ID automatically via the filter, with zero call-site
changes needed. The ID is also echoed back as an `X-Request-ID` response
header, so a report of "this specific request was slow/broke" can be
matched directly to its log lines.

**One structured line per request, uvicorn's own access log disabled**
(`--no-access-log` added to the Dockerfile CMD) — having both would just
duplicate the same information in two different, differently-shaped
formats (uvicorn's plaintext vs. this JSON), and the plaintext one carries
no request ID.

**A catch-all exception handler, verified not to shadow FastAPI's own
`HTTPException` handling** — `@app.exception_handler(Exception)` logs the
full traceback (with request ID) and returns a generic `{"detail":
"Internal server error"}` rather than leaking internals to the client.
This registers for the base `Exception` class, and `HTTPException` is a
subclass of it, which raised a real question before trusting this: does
Starlette's exception-handler lookup prefer the more specific
`HTTPException` handler FastAPI already registers, or does adding a
broader `Exception` handler intercept every `HTTPException` too (which
would turn every existing 401/403/404/422 in the test suite into a 500)?
Starlette resolves this by walking `type(exc).__mro__` and returning the
first registered handler found — i.e. most-specific-wins, not
registration-order — so the existing `HTTPException` handler still fires
for `HTTPException`s, and the new one only catches what nothing more
specific already handles. Verified empirically, not just by reading
Starlette's source: the full test suite (all HTTPException-raising
401/403/404/422 tests included) still passes after adding this handler.

## Decision

- `services/api/src/api/logging_config.py`: `configure_logging()` (call
  once at import time in `main.py`, replaces root logger handlers with one
  JSON-formatting `StreamHandler(stdout)`), `log_request()` helper, the
  `RequestIdFilter`, and the `request_id_var` ContextVar other modules can
  import if they ever need to read the current request's ID directly.
- `services/api/src/api/main.py`: calls `configure_logging()` before
  constructing `FastAPI()`; adds the request-ID/logging middleware and the
  catch-all exception handler.
- `services/api/Dockerfile`: `--no-access-log` added to the uvicorn CMD.

## Consequences

- Every request now produces one aggregatable JSON log line
  (`timestamp`, `level`, `logger`, `message`, `request_id`, plus
  `method`/`path`/`status_code`/`duration_ms` for the per-request summary
  line) instead of unconfigured, unstructured output.
- Any unhandled exception is now guaranteed to be logged with a full
  traceback and its request ID, and the client gets a safe generic message
  instead of a raw traceback or an unformatted 500.
- This is the foundation Sentry (Priority 2, item 4) builds on next —
  Sentry's SDK captures the same unhandled exceptions this handler already
  logs, with the same request correlation available via its own
  context/tags.
