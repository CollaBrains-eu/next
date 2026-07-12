"""Outbound transactional email (Phase 27, onboarding).

Same best-effort contract as signal_client.py: not configured (no SMTP
host) means every caller must treat a send as a no-op, never a hard
failure -- onboarding a user must not break because a mailbox isn't set
up yet. `smtplib` is blocking, so the actual send runs in a thread via
`asyncio.to_thread` rather than pulling in an async SMTP dependency for
one call site.
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.config import settings

logger = logging.getLogger(__name__)


def _send_sync(*, to_address: str, subject: str, html_body: str, text_body: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address
    message["To"] = to_address
    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_from_address, [to_address], message.as_string())


async def send_email(*, to_address: str, subject: str, html_body: str, text_body: str) -> bool:
    """Returns whether the email was actually sent (False if SMTP isn't
    configured, or the send itself failed) -- callers that need to report
    success/failure to an admin (e.g. resend-welcome) use the return
    value; callers that don't care can ignore it, same as send_signal_message."""
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        return False

    try:
        await asyncio.to_thread(
            _send_sync, to_address=to_address, subject=subject, html_body=html_body, text_body=text_body
        )
        return True
    except Exception:  # noqa: BLE001 - best-effort send, caller decides how to react to False
        logger.exception("Failed to send email to %s", to_address)
        return False
