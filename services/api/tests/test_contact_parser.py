from api.contact_parser import looks_like_garbage_title, parse_phone


def test_parse_phone_normalizes_dutch_landline():
    assert parse_phone("tel. 010-1234567") == "010-1234567"


def test_parse_phone_normalizes_international_format():
    assert parse_phone("Phone: +31 6 12345678") == "+31 6 12345678"


def test_parse_phone_rejects_too_few_digits():
    assert parse_phone("kamer 12") is None


def test_parse_phone_rejects_email_snippet():
    assert parse_phone("info@acme-corp-2026.com") is None


def test_parse_phone_returns_none_for_empty_string():
    assert parse_phone("") is None


def test_looks_like_garbage_title_rejects_email():
    assert looks_like_garbage_title("info@acme.com") is True


def test_looks_like_garbage_title_rejects_url():
    assert looks_like_garbage_title("https://acme.com") is True


def test_looks_like_garbage_title_rejects_overly_long_text():
    assert looks_like_garbage_title("x" * 150) is True


def test_looks_like_garbage_title_accepts_normal_title():
    assert looks_like_garbage_title("Directeur") is False


def test_looks_like_garbage_title_rejects_empty_string():
    assert looks_like_garbage_title("") is True
