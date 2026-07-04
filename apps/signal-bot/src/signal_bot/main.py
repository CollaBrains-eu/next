"""Signal bot: text-chat and document-upload bridge for CollaBrains.

Polls signal-cli-rest-api for incoming messages, resolves the sender's
phone number (Signal's sealed-sender behavior often only gives us a UUID,
so a `/v1/contacts` lookup is needed -- see
docs/adr/0006-phase3b-signal-identity-linking.md), and either:
  - forwards a text message to /chat and replies with the answer, or
  - downloads an attachment and uploads it to /documents, acknowledging
    receipt immediately (docs/adr/0007-phase3c-signal-attachments-notifications.md).
    The document pipeline notifies the sender on Signal itself once
    processing finishes -- this bot does not poll for completion.
Unlinked numbers get a clear explanation instead of a generic error, for
either kind of message.
"""
import logging
import os
import time
import urllib.parse

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("signal_bot")

SIGNAL_CLI_URL = os.environ.get("SIGNAL_CLI_URL", "http://signal-cli:8080")
SIGNAL_PHONE_NUMBER = os.environ["SIGNAL_PHONE_NUMBER"]
COLLABRAINS_API_URL = os.environ.get("COLLABRAINS_API_URL", "http://api:8000")
SIGNAL_BOT_API_TOKEN = os.environ["SIGNAL_BOT_API_TOKEN"]
POLL_INTERVAL_SECONDS = float(os.environ.get("SIGNAL_POLL_INTERVAL_SECONDS", "3"))
# A sealed-sender envelope can arrive before signal-cli's own contact sync
# has recorded that UUID's phone number yet -- retrying a few times with a
# short delay covers that race instead of prematurely telling an
# actually-linked sender they're unlinked (a real incident: see the
# 2026-07-03 08:37:44 log entry referenced in the fix's ADR).
RESOLVE_RETRY_ATTEMPTS = int(os.environ.get("SIGNAL_RESOLVE_RETRY_ATTEMPTS", "3"))
RESOLVE_RETRY_DELAY_SECONDS = float(os.environ.get("SIGNAL_RESOLVE_RETRY_DELAY_SECONDS", "2"))

FALLBACK_REPLY = "Sorry, something went wrong answering that. Please try again shortly."
UNLINKED_REPLY = (
    "This phone number isn't linked to a CollaBrains account yet. Log in to CollaBrains "
    "and set your phone number in your profile (PUT /auth/me/phone) to use this chat."
)
UPLOAD_ACK_REPLY = "Got it — processing your document now. I'll message you here once it's ready."
UPLOAD_FAILED_REPLY = "Sorry, I couldn't upload that document. Please try again shortly."

# uuid -> phone number, populated from signal-cli's contact store as senders are seen.
# Simple in-process cache: this account's contact list only grows, never needs invalidating.
_uuid_to_number: dict[str, str] = {}


def _encoded_number() -> str:
    return urllib.parse.quote(SIGNAL_PHONE_NUMBER, safe="")


def _receive_url() -> str:
    return f"{SIGNAL_CLI_URL}/v1/receive/{_encoded_number()}"


def _auth_headers(phone_number: str) -> dict:
    return {"Authorization": f"Bearer {SIGNAL_BOT_API_TOKEN}", "X-On-Behalf-Of-Phone": phone_number}


def fetch_messages(client: httpx.Client) -> list[dict]:
    response = client.get(_receive_url(), timeout=30.0)
    response.raise_for_status()
    return response.json()


def extract_message(envelope: dict) -> tuple[str, str] | None:
    """Return (sender_identifier, text) for a plain text DM (no attachments), or None to skip."""
    inner = envelope.get("envelope", {})
    data_message = inner.get("dataMessage")
    if not data_message or not data_message.get("message") or data_message.get("attachments"):
        return None

    sender = inner.get("sourceNumber") or inner.get("source")
    if not sender:
        return None

    return sender, data_message["message"]


def extract_attachments(envelope: dict) -> tuple[str, list[dict], str | None] | None:
    """Return (sender_identifier, attachments, caption) for a message with attachments, or None."""
    inner = envelope.get("envelope", {})
    data_message = inner.get("dataMessage")
    if not data_message or not data_message.get("attachments"):
        return None

    sender = inner.get("sourceNumber") or inner.get("source")
    if not sender:
        return None

    return sender, data_message["attachments"], data_message.get("message")


def resolve_phone_number(client: httpx.Client, sender: str) -> str | None:
    """Resolve a sender identifier to an E.164 phone number, or None if it can't be resolved.

    Retries the /v1/contacts refresh a few times (RESOLVE_RETRY_ATTEMPTS,
    RESOLVE_RETRY_DELAY_SECONDS apart) when the UUID isn't found -- a
    genuine network/API error still gives up immediately, since retrying
    that wouldn't help."""
    if sender.startswith("+"):
        return sender
    if sender in _uuid_to_number:
        return _uuid_to_number[sender]

    for attempt in range(RESOLVE_RETRY_ATTEMPTS):
        try:
            response = client.get(f"{SIGNAL_CLI_URL}/v1/contacts/{_encoded_number()}", timeout=15.0)
            response.raise_for_status()
            for contact in response.json():
                if contact.get("uuid") and contact.get("number"):
                    _uuid_to_number[contact["uuid"]] = contact["number"]
        except Exception:
            logger.exception("failed to fetch contacts to resolve sender %s", sender)
            return None

        if sender in _uuid_to_number:
            return _uuid_to_number[sender]

        if attempt < RESOLVE_RETRY_ATTEMPTS - 1:
            time.sleep(RESOLVE_RETRY_DELAY_SECONDS)

    return None


def ask_collabrains(client: httpx.Client, message: str, phone_number: str) -> tuple[str, bool]:
    """Returns (answer_text, was_forbidden)."""
    response = client.post(
        f"{COLLABRAINS_API_URL}/chat",
        json={"message": message},
        headers=_auth_headers(phone_number),
        timeout=120.0,
    )
    if response.status_code == 403:
        return UNLINKED_REPLY, True
    response.raise_for_status()
    return response.json()["answer"], False


def download_attachment(client: httpx.Client, attachment_id: str) -> bytes:
    response = client.get(f"{SIGNAL_CLI_URL}/v1/attachments/{attachment_id}", timeout=60.0)
    response.raise_for_status()
    return response.content


def upload_document(
    client: httpx.Client, phone_number: str, filename: str, content: bytes, content_type: str
) -> int:
    """Returns the HTTP status code -- caller decides how to react."""
    response = client.post(
        f"{COLLABRAINS_API_URL}/documents",
        files={"file": (filename, content, content_type)},
        headers=_auth_headers(phone_number),
        timeout=60.0,
    )
    return response.status_code


def handle_text_message(client: httpx.Client, sender: str, text: str) -> None:
    phone_number = resolve_phone_number(client, sender)
    if phone_number is None:
        send_reply(client, sender, UNLINKED_REPLY)
        return

    try:
        answer, _forbidden = ask_collabrains(client, text, phone_number)
    except Exception:
        logger.exception("chat request failed for message from %s", sender)
        answer = FALLBACK_REPLY

    send_reply(client, sender, answer)


def handle_attachment_message(client: httpx.Client, sender: str, attachments: list[dict], caption: str | None) -> None:
    phone_number = resolve_phone_number(client, sender)
    if phone_number is None:
        send_reply(client, sender, UNLINKED_REPLY)
        return

    for attachment in attachments:
        attachment_id = attachment.get("id")
        if not attachment_id:
            logger.warning("attachment from %s has no id, skipping: %r", sender, attachment)
            continue

        filename = attachment.get("filename") or f"signal-{attachment_id}"
        content_type = attachment.get("contentType") or "application/octet-stream"
        if caption:
            filename = f"{caption.strip()[:200]} - {filename}"

        try:
            content = download_attachment(client, attachment_id)
            status_code = upload_document(client, phone_number, filename, content, content_type)
        except Exception:
            logger.exception("failed to upload attachment %s from %s", attachment_id, sender)
            send_reply(client, sender, UPLOAD_FAILED_REPLY)
            return

        if status_code == 403:
            send_reply(client, sender, UNLINKED_REPLY)
            return
        if status_code >= 400:
            logger.error("upload of attachment %s from %s failed with status %s", attachment_id, sender, status_code)
            send_reply(client, sender, UPLOAD_FAILED_REPLY)
            return

    send_reply(client, sender, UPLOAD_ACK_REPLY)


def send_reply(client: httpx.Client, recipient: str, text: str) -> None:
    try:
        response = client.post(
            f"{SIGNAL_CLI_URL}/v2/send",
            json={"message": text, "number": SIGNAL_PHONE_NUMBER, "recipients": [recipient]},
            timeout=30.0,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("failed to send reply to %s", recipient)


def handle_envelope(client: httpx.Client, envelope: dict) -> None:
    attachment_parsed = extract_attachments(envelope)
    if attachment_parsed is not None:
        sender, attachments, caption = attachment_parsed
        logger.info("received %d attachment(s) from %s", len(attachments), sender)
        handle_attachment_message(client, sender, attachments, caption)
        return

    text_parsed = extract_message(envelope)
    if text_parsed is not None:
        sender, text = text_parsed
        logger.info("received message from %s", sender)
        handle_text_message(client, sender, text)


def run() -> None:
    logger.info("signal-bot starting, number=%s, polling every %ss", SIGNAL_PHONE_NUMBER, POLL_INTERVAL_SECONDS)
    with httpx.Client() as client:
        while True:
            try:
                for envelope in fetch_messages(client):
                    handle_envelope(client, envelope)
            except Exception:
                logger.exception("poll cycle failed, will retry")
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
