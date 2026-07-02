"""Signal bot: text-chat bridge between Signal and the CollaBrains AI Gateway.

Polls signal-cli-rest-api for incoming messages, resolves the sender's
phone number (Signal's sealed-sender behavior often only gives us a UUID,
so a `/v1/contacts` lookup is needed -- see
docs/adr/0006-phase3b-signal-identity-linking.md), forwards each message
to the CollaBrains /chat orchestrator on that sender's behalf, and sends
the answer back on Signal. Unlinked numbers get a clear explanation
instead of a generic error.
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

FALLBACK_REPLY = "Sorry, something went wrong answering that. Please try again shortly."
UNLINKED_REPLY = (
    "This phone number isn't linked to a CollaBrains account yet. Log in to CollaBrains "
    "and set your phone number in your profile (PUT /auth/me/phone) to use this chat."
)

# uuid -> phone number, populated from signal-cli's contact store as senders are seen.
# Simple in-process cache: this account's contact list only grows, never needs invalidating.
_uuid_to_number: dict[str, str] = {}


def _encoded_number() -> str:
    return urllib.parse.quote(SIGNAL_PHONE_NUMBER, safe="")


def _receive_url() -> str:
    return f"{SIGNAL_CLI_URL}/v1/receive/{_encoded_number()}"


def fetch_messages(client: httpx.Client) -> list[dict]:
    response = client.get(_receive_url(), timeout=30.0)
    response.raise_for_status()
    return response.json()


def extract_message(envelope: dict) -> tuple[str, str] | None:
    """Return (sender_identifier, text) for a plain text DM, or None to skip this envelope.

    `sender_identifier` is a phone number when Signal provides one, otherwise the
    sender's UUID -- resolve it via `resolve_phone_number` before calling /chat.
    """
    inner = envelope.get("envelope", {})
    data_message = inner.get("dataMessage")
    if not data_message or not data_message.get("message"):
        return None

    sender = inner.get("sourceNumber") or inner.get("source")
    if not sender:
        return None

    return sender, data_message["message"]


def resolve_phone_number(client: httpx.Client, sender: str) -> str | None:
    """Resolve a sender identifier to an E.164 phone number, or None if it can't be resolved."""
    if sender.startswith("+"):
        return sender
    if sender in _uuid_to_number:
        return _uuid_to_number[sender]

    try:
        response = client.get(f"{SIGNAL_CLI_URL}/v1/contacts/{_encoded_number()}", timeout=15.0)
        response.raise_for_status()
        for contact in response.json():
            if contact.get("uuid") and contact.get("number"):
                _uuid_to_number[contact["uuid"]] = contact["number"]
    except Exception:
        logger.exception("failed to fetch contacts to resolve sender %s", sender)
        return None

    return _uuid_to_number.get(sender)


def ask_collabrains(client: httpx.Client, message: str, phone_number: str) -> tuple[str, bool]:
    """Returns (answer_text, was_forbidden)."""
    response = client.post(
        f"{COLLABRAINS_API_URL}/chat",
        json={"message": message},
        headers={
            "Authorization": f"Bearer {SIGNAL_BOT_API_TOKEN}",
            "X-On-Behalf-Of-Phone": phone_number,
        },
        timeout=120.0,
    )
    if response.status_code == 403:
        return UNLINKED_REPLY, True
    response.raise_for_status()
    return response.json()["answer"], False


def send_reply(client: httpx.Client, recipient: str, text: str) -> None:
    response = client.post(
        f"{SIGNAL_CLI_URL}/v2/send",
        json={"message": text, "number": SIGNAL_PHONE_NUMBER, "recipients": [recipient]},
        timeout=30.0,
    )
    response.raise_for_status()


def handle_envelope(client: httpx.Client, envelope: dict) -> None:
    parsed = extract_message(envelope)
    if parsed is None:
        return
    sender, text = parsed
    logger.info("received message from %s", sender)

    phone_number = resolve_phone_number(client, sender)
    if phone_number is None:
        logger.warning("could not resolve a phone number for sender %s, replying with unlinked message", sender)
        answer = UNLINKED_REPLY
    else:
        try:
            answer, forbidden = ask_collabrains(client, text, phone_number)
            if forbidden:
                logger.info("phone number %s is not linked to a CollaBrains account", phone_number)
        except Exception:
            logger.exception("chat request failed for message from %s", sender)
            answer = FALLBACK_REPLY

    try:
        send_reply(client, sender, answer)
    except Exception:
        logger.exception("failed to send reply to %s", sender)


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
