import os

os.environ.setdefault("SIGNAL_PHONE_NUMBER", "+15550001111")
os.environ.setdefault("SIGNAL_BOT_API_TOKEN", "test-token")

from signal_bot.main import _receive_url, extract_text_message  # noqa: E402


def test_receive_url_encodes_the_plus_sign():
    url = _receive_url()
    assert url.endswith("/v1/receive/%2B15550001111")


def test_extract_text_message_returns_sender_and_text():
    envelope = {
        "envelope": {
            "sourceNumber": "+15559998888",
            "dataMessage": {"message": "hello there"},
        }
    }
    assert extract_text_message(envelope) == ("+15559998888", "hello there")


def test_extract_text_message_falls_back_to_uuid_source():
    """Sealed-sender messages have no sourceNumber, only a UUID `source` (ADR 0005)."""
    envelope = {
        "envelope": {
            "source": "f080a563-d3a2-459a-938c-2ac9497d35bd",
            "dataMessage": {"message": "hi"},
        }
    }
    assert extract_text_message(envelope) == ("f080a563-d3a2-459a-938c-2ac9497d35bd", "hi")


def test_extract_text_message_skips_non_text_envelopes():
    assert extract_text_message({"envelope": {"sourceNumber": "+1555", "typingMessage": {}}}) is None
    assert extract_text_message({"envelope": {"dataMessage": {"message": "hi"}}}) is None
    assert extract_text_message({"envelope": {}}) is None
    assert extract_text_message({}) is None


def test_extract_text_message_skips_attachment_only_messages():
    envelope = {
        "envelope": {
            "sourceNumber": "+15559998888",
            "dataMessage": {"message": None, "attachments": [{"filename": "photo.jpg"}]},
        }
    }
    assert extract_text_message(envelope) is None
