from api.text_language import detect_document_language, ts_config_for_preferred_language

ENGLISH_TEXT = (
    "This agreement is entered into by and between the parties for the "
    "purpose of establishing the terms and conditions governing their "
    "ongoing business relationship, including payment schedules."
)
DUTCH_TEXT = (
    "Deze overeenkomst wordt aangegaan door en tussen de partijen met als "
    "doel de voorwaarden vast te stellen die hun voortdurende zakelijke "
    "relatie beheersen, met inbegrip van betalingsschema's."
)
GERMAN_TEXT = (
    "Dieser Vertrag wird zwischen den Parteien geschlossen, um die "
    "Bedingungen festzulegen und zu regeln, die ihre laufende "
    "Geschaeftsbeziehung bestimmen, einschliesslich der Zahlungsplaene."
)


def test_detects_english():
    assert detect_document_language(ENGLISH_TEXT) == "english"


def test_detects_dutch():
    assert detect_document_language(DUTCH_TEXT) == "dutch"


def test_detects_german():
    assert detect_document_language(GERMAN_TEXT) == "german"


def test_falls_back_to_english_for_empty_text():
    assert detect_document_language("") == "english"


def test_falls_back_to_english_for_text_too_short_to_be_reliable():
    # langdetect is unreliable on very short strings (confirmed: "ok" alone
    # detects as Slovak) -- below the length floor we don't trust it.
    assert detect_document_language("ok") == "english"


def test_falls_back_to_english_for_an_unsupported_detected_language():
    french_text = (
        "Cet accord est conclu entre les parties dans le but d'etablir les "
        "conditions qui regissent leur relation commerciale continue et "
        "les modalites de paiement associees a ce contrat."
    )
    assert detect_document_language(french_text) == "english"


def test_ts_config_maps_known_preferred_languages():
    assert ts_config_for_preferred_language("English") == "english"
    assert ts_config_for_preferred_language("Nederlands") == "dutch"
    assert ts_config_for_preferred_language("Deutsch") == "german"


def test_ts_config_falls_back_to_english_for_none_or_unknown():
    assert ts_config_for_preferred_language(None) == "english"
    assert ts_config_for_preferred_language("Klingon") == "english"
