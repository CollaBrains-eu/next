"""Signal bot: text-chat bridge between Signal and the CollaBrains AI Gateway.

Polls signal-cli-rest-api for incoming messages, forwards each to the
CollaBrains /chat orchestrator, and sends the answer back on Signal. See
docs/adr/0005-phase3a-signal-bot.md for scope (text-only, one shared
service identity, no attachments/notifications yet).
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


def _receive_url() -> str:
    encoded_number = urllib.parse.quote(SIGNAL_PHONE_NUMBER, safe="")
    return f"{SIGNAL_CLI_URL}/v1/receive/{encoded_number}"


def fetch_messages(client: httpx.Client) -> list[dict]:
    response = client.get(_receive_url(), timeout=30.0)
    response.raise_for_status()
    return response.json()


def extract_text_message(envelope: dict) -> tuple[str, str] | None:
    """Return (sender, text) for a plain text DM, or None to skip this envelope."""
    inner = envelope.get("envelope", {})
    data_message = inner.get("dataMessage")
    if not data_message or not data_message.get("message"):
        return None

    sender = inner.get("sourceNumber") or inner.get("source")
    if not sender:
        return None

    return sender, data_message["message"]


def ask_collabrains(client: httpx.Client, message: str) -> str:
    response = client.post(
        f"{COLLABRAINS_API_URL}/chat",
        json={"message": message},
        headers={"Authorization": f"Bearer {SIGNAL_BOT_API_TOKEN}"},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["answer"]


def send_reply(client: httpx.Client, recipient: str, text: str) -> None:
    response = client.post(
        f"{SIGNAL_CLI_URL}/v2/send",
        json={"message": text, "number": SIGNAL_PHONE_NUMBER, "recipients": [recipient]},
        timeout=30.0,
    )
    response.raise_for_status()


def handle_envelope(client: httpx.Client, envelope: dict) -> None:
    parsed = extract_text_message(envelope)
    if parsed is None:
        return
    sender, text = parsed
    logger.info("received message from %s", sender)

    try:
        answer = ask_collabrains(client, text)
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
