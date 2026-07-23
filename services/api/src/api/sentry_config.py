"""Sentry error tracking. ADR 0072 (Priority 2, item 4).

Privacy-conscious by design, not just by SDK default: this app handles
addresses, phone numbers, legal documents, and OCR'd personal data (see
document tags like "personal_data"/"client_profile" in api/documents.py), so
the generic Sentry-recommended `send_default_pii=True` is deliberately
overridden to False here, and stack-trace local-variable capture is
disabled entirely -- a traceback for a bug in, say, address parsing could
otherwise put a real street address into Sentry as a local variable value.
"""

import re

import sentry_sdk
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

from api.config import settings

# Beyond Sentry's own default denylist (password, secret, token, etc.), this
# app's domain adds fields worth scrubbing defensively if they ever end up as
# exception context (e.g. function arguments logged via `extra=`) despite
# include_local_variables=False already covering stack-frame locals.
_ADDITIONAL_SENSITIVE_FIELDS = [
    "ocr_text",
    "address",
    "street",
    "postal_code",
    "phone_number",
    "bsn",
    "iban",
]

# Neither the denylist above nor include_local_variables=False touches an
# exception's own message text -- `raise ValueError(f"bad address: {addr}")`
# puts a real address straight into Sentry regardless of either setting,
# since scrubbing can only act on known structured fields (header/local-var
# *names*), not arbitrary free text. Best-effort pattern redaction for this
# app's specific known-sensitive shapes as a second layer -- not
# exhaustive, and not a substitute for not interpolating raw user data into
# exception messages in the first place.
_DUTCH_POSTAL_CODE = re.compile(r"\b\d{4}\s?[A-Za-z]{2}\b")
_DUTCH_BSN = re.compile(r"\b\d{9}\b")
_IBAN = re.compile(r"\b[A-Za-z]{2}\d{2}[A-Za-z0-9]{10,30}\b")
_PHONE = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(0\)|0)?\d{9,10}\b")


def _redact_text(value: str) -> str:
    value = _IBAN.sub("[REDACTED-IBAN]", value)
    value = _DUTCH_POSTAL_CODE.sub("[REDACTED-POSTAL-CODE]", value)
    value = _PHONE.sub("[REDACTED-PHONE]", value)
    value = _DUTCH_BSN.sub("[REDACTED-BSN]", value)
    return value


def _scrub_event_text(event: dict, _hint: dict) -> dict:
    for exc in event.get("exception", {}).get("values", []) or []:
        if exc.get("value"):
            exc["value"] = _redact_text(exc["value"])
    if event.get("message"):
        event["message"] = _redact_text(event["message"])
    return event


def init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        send_default_pii=False,
        include_local_variables=False,
        event_scrubber=EventScrubber(denylist=DEFAULT_DENYLIST + _ADDITIONAL_SENSITIVE_FIELDS),
        before_send=_scrub_event_text,
        traces_sample_rate=1.0,
    )
