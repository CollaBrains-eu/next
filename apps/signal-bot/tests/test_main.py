import os
from unittest.mock import MagicMock

os.environ.setdefault("SIGNAL_PHONE_NUMBER", "+15550001111")
os.environ.setdefault("SIGNAL_BOT_API_TOKEN", "test-token")

import signal_bot.main as main  # noqa: E402


def test_receive_url_encodes_the_plus_sign():
    assert main._receive_url().endswith("/v1/receive/%2B15550001111")


def test_extract_message_returns_sender_and_text():
    envelope = {
        "envelope": {
            "sourceNumber": "+15559998888",
            "dataMessage": {"message": "hello there"},
        }
    }
    assert main.extract_message(envelope) == ("+15559998888", "hello there")


def test_extract_message_falls_back_to_uuid_source():
    """Sealed-sender messages have no sourceNumber, only a UUID `source` (ADR 0005)."""
    envelope = {
        "envelope": {
            "source": "f080a563-d3a2-459a-938c-2ac9497d35bd",
            "dataMessage": {"message": "hi"},
        }
    }
    assert main.extract_message(envelope) == ("f080a563-d3a2-459a-938c-2ac9497d35bd", "hi")


def test_extract_message_skips_non_text_envelopes():
    assert main.extract_message({"envelope": {"sourceNumber": "+1555", "typingMessage": {}}}) is None
    assert main.extract_message({"envelope": {"dataMessage": {"message": "hi"}}}) is None
    assert main.extract_message({"envelope": {}}) is None
    assert main.extract_message({}) is None


def test_extract_message_skips_attachment_only_messages():
    envelope = {
        "envelope": {
            "sourceNumber": "+15559998888",
            "dataMessage": {"message": None, "attachments": [{"filename": "photo.jpg"}]},
        }
    }
    assert main.extract_message(envelope) is None


def test_resolve_phone_number_passes_through_a_real_number():
    client = MagicMock()
    assert main.resolve_phone_number(client, "+15559998888") == "+15559998888"
    client.get.assert_not_called()


def test_resolve_phone_number_looks_up_and_caches_uuid_senders():
    main._uuid_to_number.clear()
    client = MagicMock()
    client.get.return_value.json.return_value = [
        {"uuid": "f080a563-d3a2-459a-938c-2ac9497d35bd", "number": "+4915110684738"}
    ]

    resolved = main.resolve_phone_number(client, "f080a563-d3a2-459a-938c-2ac9497d35bd")
    assert resolved == "+4915110684738"
    assert client.get.call_count == 1

    # second lookup for the same UUID should hit the cache, not call out again
    resolved_again = main.resolve_phone_number(client, "f080a563-d3a2-459a-938c-2ac9497d35bd")
    assert resolved_again == "+4915110684738"
    assert client.get.call_count == 1


def test_resolve_phone_number_returns_none_for_unknown_uuid():
    main._uuid_to_number.clear()
    client = MagicMock()
    client.get.return_value.json.return_value = []
    assert main.resolve_phone_number(client, "00000000-0000-0000-0000-000000000000") is None


def test_ask_collabrains_treats_403_as_unlinked():
    client = MagicMock()
    client.post.return_value.status_code = 403
    answer, forbidden = main.ask_collabrains(client, "hi", "+15559998888")
    assert forbidden is True
    assert answer == main.UNLINKED_REPLY
