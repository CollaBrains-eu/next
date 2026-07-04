import os
from unittest.mock import MagicMock, patch

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


def test_extract_message_skips_messages_that_have_attachments_even_with_text():
    """Attachment messages route through extract_attachments instead, even with a caption."""
    envelope = {
        "envelope": {
            "sourceNumber": "+15559998888",
            "dataMessage": {"message": "here's the file", "attachments": [{"id": "a1"}]},
        }
    }
    assert main.extract_message(envelope) is None


def test_extract_attachments_returns_sender_attachments_and_caption():
    envelope = {
        "envelope": {
            "sourceNumber": "+15559998888",
            "dataMessage": {
                "message": "invoice for June",
                "attachments": [{"id": "a1", "filename": "invoice.pdf", "contentType": "application/pdf"}],
            },
        }
    }
    sender, attachments, caption = main.extract_attachments(envelope)
    assert sender == "+15559998888"
    assert attachments == [{"id": "a1", "filename": "invoice.pdf", "contentType": "application/pdf"}]
    assert caption == "invoice for June"


def test_extract_attachments_returns_none_caption_when_no_text():
    envelope = {
        "envelope": {"sourceNumber": "+15559998888", "dataMessage": {"attachments": [{"id": "a1"}]}}
    }
    sender, attachments, caption = main.extract_attachments(envelope)
    assert caption is None


def test_extract_attachments_skips_text_only_messages():
    envelope = {"envelope": {"sourceNumber": "+1555", "dataMessage": {"message": "hi"}}}
    assert main.extract_attachments(envelope) is None


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
    with patch.object(main.time, "sleep"):
        assert main.resolve_phone_number(client, "00000000-0000-0000-0000-000000000000") is None
    assert client.get.call_count == main.RESOLVE_RETRY_ATTEMPTS


def test_resolve_phone_number_retries_before_giving_up_on_transient_contact_sync_lag():
    """A sealed-sender UUID that isn't in signal-cli's contacts yet on the
    first try (but shows up moments later) should still resolve -- the real
    incident this covers: a linked user got told they were unlinked because
    the very first lookup raced signal-cli's own contact sync."""
    main._uuid_to_number.clear()
    client = MagicMock()
    client.get.return_value.json.side_effect = [
        [],
        [],
        [{"uuid": "f080a563-d3a2-459a-938c-2ac9497d35bd", "number": "+4915110684738"}],
    ]

    with patch.object(main.time, "sleep") as mock_sleep:
        resolved = main.resolve_phone_number(client, "f080a563-d3a2-459a-938c-2ac9497d35bd")

    assert resolved == "+4915110684738"
    assert client.get.call_count == 3
    assert mock_sleep.call_count == 2


def test_resolve_phone_number_gives_up_immediately_on_a_genuine_api_error():
    main._uuid_to_number.clear()
    client = MagicMock()
    client.get.side_effect = Exception("connection refused")

    with patch.object(main.time, "sleep") as mock_sleep:
        assert main.resolve_phone_number(client, "f080a563-d3a2-459a-938c-2ac9497d35bd") is None

    assert client.get.call_count == 1
    mock_sleep.assert_not_called()


def test_ask_collabrains_treats_403_as_unlinked():
    client = MagicMock()
    client.post.return_value.status_code = 403
    answer, forbidden = main.ask_collabrains(client, "hi", "+15559998888")
    assert forbidden is True
    assert answer == main.UNLINKED_REPLY


def test_handle_attachment_message_uploads_each_attachment_and_acks(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(main, "resolve_phone_number", lambda c, sender: "+15559998888")
    monkeypatch.setattr(main, "download_attachment", lambda c, attachment_id: b"filebytes")
    upload_calls = []

    def fake_upload(c, phone_number, filename, content, content_type):
        upload_calls.append((phone_number, filename, content, content_type))
        return 202

    monkeypatch.setattr(main, "upload_document", fake_upload)
    sent = []
    monkeypatch.setattr(main, "send_reply", lambda c, recipient, text: sent.append((recipient, text)))

    main.handle_attachment_message(
        client, "+15559998888", [{"id": "a1", "filename": "invoice.pdf", "contentType": "application/pdf"}], "June"
    )

    assert len(upload_calls) == 1
    phone_number, filename, content, content_type = upload_calls[0]
    assert phone_number == "+15559998888"
    assert filename == "June - invoice.pdf"
    assert content == b"filebytes"
    assert sent == [("+15559998888", main.UPLOAD_ACK_REPLY)]


def test_handle_attachment_message_sends_unlinked_reply_when_upload_forbidden(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(main, "resolve_phone_number", lambda c, sender: "+15559998888")
    monkeypatch.setattr(main, "download_attachment", lambda c, attachment_id: b"filebytes")
    monkeypatch.setattr(main, "upload_document", lambda *a, **kw: 403)
    sent = []
    monkeypatch.setattr(main, "send_reply", lambda c, recipient, text: sent.append((recipient, text)))

    main.handle_attachment_message(client, "+15559998888", [{"id": "a1", "filename": "x.pdf"}], None)

    assert sent == [("+15559998888", main.UNLINKED_REPLY)]


def test_handle_attachment_message_replies_unlinked_when_sender_unresolved(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(main, "resolve_phone_number", lambda c, sender: None)
    sent = []
    monkeypatch.setattr(main, "send_reply", lambda c, recipient, text: sent.append((recipient, text)))

    main.handle_attachment_message(client, "some-uuid", [{"id": "a1"}], None)

    assert sent == [("some-uuid", main.UNLINKED_REPLY)]
