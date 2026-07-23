"""Deterministic address parsing + maps-link building.

Splits address *recognition* (entity_agent.py's LLM call: "is this text an
address?") from *parsing* (this module: "what are its structured fields?").
Live production data showed the LLM reliably spots address-shaped text but
almost never fills in the structured fields itself (1/15 real extractions
had any field populated) -- see
docs/superpowers/specs/2026-07-23-reliable-entity-extraction-maps-design.md.
A small local model doing both semantic identification AND precise field
splitting in one pass is the likely cause; this module does the splitting
with plain regex instead, which is far more reliable for the fixed,
recognizable NL/DE postal-code formats this app's real documents use.

Scoped to NL ("9671 CT", 4 digits + 2 letters) and DE ("26831", 5 digits)
formats only -- the two seen in production so far, not a general
international address parser (YAGNI).
"""
import re
from urllib.parse import quote

_NL_POSTAL = r"\d{4}\s?[A-Z]{2}"
_DE_POSTAL = r"\d{5}"
_STREET_NUMBER = r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.\-' ]*?\s+\d+[A-Za-z]?"
_TRAILING_NUMBER = re.compile(r"\d+[A-Za-z]?$")

_FULL_NL_RE = re.compile(rf"({_STREET_NUMBER}),?\s+({_NL_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_FULL_DE_RE = re.compile(rf"({_STREET_NUMBER}),?\s+({_DE_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_POSTAL_CITY_NL_RE = re.compile(rf"({_NL_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_POSTAL_CITY_DE_RE = re.compile(rf"({_DE_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_STREET_NUMBER_RE = re.compile(rf"({_STREET_NUMBER})", re.IGNORECASE)


def _split_street_number(street_number: str) -> tuple[str, str | None]:
    number_match = _TRAILING_NUMBER.search(street_number)
    if not number_match:
        return street_number.strip(), None
    return street_number[: number_match.start()].strip(), number_match.group(0)


def parse_address(raw_text: str) -> dict[str, str | None]:
    """Best-effort split of an address-shaped string into structured fields.
    Any field not confidently parsed stays None -- never guessed."""
    text = raw_text.strip()
    result: dict[str, str | None] = {
        "street": None, "house_number": None, "postal_code": None, "city": None, "country": None,
    }

    for regex, country in ((_FULL_NL_RE, "NL"), (_FULL_DE_RE, "DE")):
        match = regex.search(text)
        if match:
            street, house_number = _split_street_number(match.group(1).strip())
            result["street"] = street
            result["house_number"] = house_number
            result["postal_code"] = match.group(2).upper() if country == "NL" else match.group(2)
            result["city"] = match.group(3).strip()
            result["country"] = country
            return result

    for regex, country in ((_POSTAL_CITY_NL_RE, "NL"), (_POSTAL_CITY_DE_RE, "DE")):
        match = regex.search(text)
        if match:
            result["postal_code"] = match.group(1).upper() if country == "NL" else match.group(1)
            result["city"] = match.group(2).strip()
            result["country"] = country
            return result

    street_match = _STREET_NUMBER_RE.search(text)
    if street_match:
        street, house_number = _split_street_number(street_match.group(1).strip())
        if house_number:
            result["street"] = street
            result["house_number"] = house_number

    return result


def find_full_address_matches(text: str) -> list[str]:
    """Scan raw text for high-confidence full address matches (street+number+
    postal+city together) -- a recall safety net for addresses the LLM's
    semantic pass didn't propose as a candidate at all. Deliberately uses
    only the strict _FULL_NL_RE/_FULL_DE_RE patterns (all four parts
    present), not the looser postal-only or street-only fallbacks
    parse_address() also tries -- scanning arbitrary document prose with a
    loose pattern would flag invoice numbers, case numbers, etc. as false
    positives.
    """
    matches = []
    for regex in (_FULL_NL_RE, _FULL_DE_RE):
        for match in regex.finditer(text):
            matches.append(match.group(0).strip())
    return matches


def build_maps_url(
    *, street: str | None, house_number: str | None, postal_code: str | None,
    city: str | None, country: str | None,
) -> str | None:
    """Google Maps universal search link -- works with or without the app
    installed, no API key needed. Returns None if there isn't enough data
    to build a meaningful query (callers must not show/send a link then)."""
    if not any([street, postal_code, city]):
        return None
    parts = [
        " ".join(p for p in (street, house_number) if p) or None,
        postal_code,
        city,
        country,
    ]
    query = ", ".join(p for p in parts if p)
    return f"https://www.google.com/maps/search/?api=1&query={quote(query)}"
