"""
Email provider — a thin wrapper around Resend, isolated in its own app.

The rest of the project sends mail through this one small, provider-specific surface
(mirrors how `chat/ai.py` isolates the Anthropic SDK). It knows nothing about chat —
callers pass plain `(to, subject, text)`.

Feature-gated on `RESEND_API_KEY`: with no key set the app still runs — `send_email`
logs the intended message and returns False instead of raising, exactly like the AI
feature degrades without `ANTHROPIC_API_KEY`. So local dev and key-less prod are fine.

Env:
  * RESEND_API_KEY — enables real delivery.
  * RESEND_FROM    — the From header, e.g. "Live Chat <live-chat@bilalhasson.com>".
"""

import logging
import os

logger = logging.getLogger(__name__)

# Resend's shared onboarding sender works without a verified domain for early testing;
# set RESEND_FROM to a verified address for real sending.
_DEFAULT_FROM = "Live Chat <live-chat@bilalhasson.com>"


def enabled() -> bool:
    return bool(os.environ.get("RESEND_API_KEY"))


def send_email(to: str, subject: str, text: str) -> bool:
    """Send a plain-text email via Resend. Returns True on success, False otherwise.

    Never raises: a mail failure must not break the caller (e.g. ending a chat).
    """
    if not to:
        return False
    if not enabled():
        logger.info("[mailer] RESEND_API_KEY unset — would email %s: %s", to, subject)
        return False
    try:
        import resend

        resend.api_key = os.environ["RESEND_API_KEY"]
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", _DEFAULT_FROM),
            "to": [to],
            "subject": subject,
            "text": text,
        })
        return True
    except Exception:
        logger.exception("[mailer] failed to send email to %s", to)
        return False
