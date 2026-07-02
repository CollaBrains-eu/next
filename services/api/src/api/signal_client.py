"""Outbound Signal messaging for proactive notifications (ADR 0007).

Best-effort only: every caller must treat a failure here as non-fatal.
signal-cli is gated behind the `signal` Compose profile, so it may simply
not be running, and that must never break the document pipeline.
"""
import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


async def send_signal_message(recipient_phone_number: str, text: str) -> None:
    if not settings.signal_cli_url or not settings.signal_phone_number:
        return

    async with httpx.AsyncClient(base_url=settings.signal_cli_url, timeout=30.0) as client:
        response = await client.post(
            "/v2/send",
            json={
                "message": text,
                "number": settings.signal_phone_number,
                "recipients": [recipient_phone_number],
            },
        )
        response.raise_for_status()
