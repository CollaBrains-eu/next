"""Vehicle Agent: regex-detect kentekens/VINs in document text, enrich
from RDW, and link matching vehicles across documents (Phase 18).

Detection is deliberately regex, not LLM-based -- see
docs/superpowers/specs/2026-07-04-vehicle-entity-design.md for why:
Dutch kentekens and VINs follow strict, small, fixed syntactic formats,
which a deterministic pattern matches more reliably (and for free) than
an LLM prompt. This covers the commonly-used NL kenteken "sidecodes";
older/rarer historical formats are not exhaustively covered -- an
accepted, documented limitation, not a bug.
"""
import re

_SEP = r"[-\s]?"
_KENTEKEN_PATTERNS = [
    rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}",  # XX-99-XX
    rf"\d{{2}}{_SEP}[A-Z]{{2}}{_SEP}\d{{2}}",  # 99-XX-99
    rf"\d{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}",  # 99-99-XX
    rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}",  # XX-99-99
    rf"\d{{2}}{_SEP}[A-Z]{{3}}{_SEP}\d{{1}}",  # 99-XXX-9
    rf"\d{{1}}{_SEP}[A-Z]{{3}}{_SEP}\d{{2}}",  # 9-XXX-99
    rf"[A-Z]{{2}}{_SEP}\d{{3}}{_SEP}[A-Z]{{1}}",  # XX-999-X
    rf"[A-Z]{{1}}{_SEP}\d{{3}}{_SEP}[A-Z]{{2}}",  # X-999-XX
]
KENTEKEN_RE = re.compile(r"\b(?:" + "|".join(_KENTEKEN_PATTERNS) + r")\b", re.IGNORECASE)
# 17-char VIN per ISO 3779, excluding I/O/Q (never used, to avoid 1/0 confusion).
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)


def _normalize_kenteken(raw: str) -> str:
    return raw.upper().replace("-", "").replace(" ", "")


def detect_kentekens(text: str) -> list[str]:
    return sorted({_normalize_kenteken(match) for match in KENTEKEN_RE.findall(text)})


def detect_vins(text: str) -> list[str]:
    return sorted({match.upper() for match in VIN_RE.findall(text)})
