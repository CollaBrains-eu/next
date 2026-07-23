"""Deterministic contact-field validation (phone normalization, title guardrail).

Same split as address_parser.py: entity_agent.py's LLM call identifies "this text
near entity Y looks like a phone number / job title", this module validates and
normalizes it rather than trusting the LLM to format it correctly -- see
docs/superpowers/specs/2026-07-23-ldap-contact-details-design.md.
"""
import re

_PHONE_CHARS_RE = re.compile(r"[\d\s\-\+\(\)]{6,20}")
_PHONE_MIN_DIGITS = 7

_GARBAGE_TITLE_RE = re.compile(r"@|https?://|www\.", re.IGNORECASE)
_TITLE_MAX_LENGTH = 100


def parse_phone(raw_text: str) -> str | None:
    """Normalize a candidate phone snippet to a cleaned digits-and-symbols
    string, or None if it doesn't look like a phone number. Never guesses a
    country code or reformats into E.164 -- just strips surrounding noise and
    validates there are enough digits to plausibly be a phone number."""
    text = raw_text.strip()
    if not text or "@" in text or "http" in text.lower():
        return None
    match = _PHONE_CHARS_RE.search(text)
    if not match:
        return None
    candidate = match.group(0).strip()
    if sum(c.isdigit() for c in candidate) < _PHONE_MIN_DIGITS:
        return None
    return re.sub(r"\s{2,}", " ", candidate)


def looks_like_garbage_title(text: str) -> bool:
    """Reject title candidates that are too long or contain an email/URL --
    same guardrail pattern as entity_agent.py's _looks_like_garbage_address
    (an LLM occasionally mis-slots the wrong field's text into this one)."""
    stripped = text.strip()
    if not stripped or len(stripped) > _TITLE_MAX_LENGTH:
        return True
    return bool(_GARBAGE_TITLE_RE.search(stripped))
