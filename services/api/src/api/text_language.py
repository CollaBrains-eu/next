"""Language detection for hybrid search's keyword half.

`search_service.hybrid_search`'s keyword query was hardcoded to Postgres's
'english' text-search config, mis-stemming and failing to strip stopwords
for the German/Dutch documents and queries this platform's own locale
files (en/de/nl) say it supports. This module maps free text and the
UserPreference.preferred_language display name to a Postgres regconfig
name -- the only three CollaBrains actually ships a UI language for.
"""
from langdetect import LangDetectException, detect

_ISO_TO_TS_CONFIG = {"en": "english", "nl": "dutch", "de": "german"}
_PREFERRED_LANGUAGE_TO_TS_CONFIG = {"English": "english", "Nederlands": "dutch", "Deutsch": "german"}

DEFAULT_TS_CONFIG = "english"

# langdetect's statistical model is unreliable below this length --
# confirmed empirically: a 2-character string detects as Slovak.
_MIN_RELIABLE_LENGTH = 20


def detect_document_language(text: str) -> str:
    """A Postgres text-search config name ('english'/'german'/'dutch'),
    falling back to DEFAULT_TS_CONFIG for text too short to be reliable,
    text langdetect can't classify, or any detected language this
    platform doesn't ship a UI translation for."""
    if len(text.strip()) < _MIN_RELIABLE_LENGTH:
        return DEFAULT_TS_CONFIG
    try:
        iso_code = detect(text)
    except LangDetectException:
        return DEFAULT_TS_CONFIG
    return _ISO_TO_TS_CONFIG.get(iso_code, DEFAULT_TS_CONFIG)


def ts_config_for_preferred_language(preferred_language: str | None) -> str:
    """Same regconfig mapping, from a UserPreference.preferred_language
    display name (e.g. "Nederlands") instead of detected free text."""
    if preferred_language is None:
        return DEFAULT_TS_CONFIG
    return _PREFERRED_LANGUAGE_TO_TS_CONFIG.get(preferred_language, DEFAULT_TS_CONFIG)
