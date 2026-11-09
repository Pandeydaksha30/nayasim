"""Outgoing email for verification and password-reset links.

With NYAYASIM_SMTP_HOST set, mail goes out over SMTP with STARTTLS (port 587) or TLS (465).
Without it (local development) each message is written to data/outbox/ as a text file and its
link is logged, so the flow can be completed without a mail server. Production must set SMTP.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from app.config import settings

log = logging.getLogger("nyayasim.mail")
OUTBOX = Path(__file__).resolve().parents[3] / "data" / "outbox"


class MailError(RuntimeError):
    pass


def send_mail(to: str, subject: str, text: str, link: str | None = None) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)

    if not settings.smtp_host:
        OUTBOX.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        path = OUTBOX / f"{stamp}.txt"
        # Plain, decoded text (not the encoded MIME form) so links can be copied as they are.
        path.write_text(f"To: {to}\nSubject: {subject}\n\n{text}", encoding="utf-8")
        # Dev only: the link is printed so a developer can follow it. Never enabled with SMTP set.
        log.warning("No SMTP configured: email to %s saved to %s. Link: %s", to, path, link or "-")
        print(f"[mail] to={to} subject={subject!r} link={link or '-'} saved={path}", flush=True)
        return

    password = settings.smtp_password.get_secret_value() if settings.smtp_password else ""
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, 465, context=ssl.create_default_context(), timeout=20
            ) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                if settings.smtp_user:
                    s.login(settings.smtp_user, password)
                s.send_message(msg)
    except (OSError, smtplib.SMTPException) as e:
        # Reported to the caller (and logged without the message body); never silently dropped.
        log.error("Sending email to %s failed: %s", to, type(e).__name__)
        raise MailError("We could not send the email right now. Please try again in a few minutes.") from e
