"""
Compose and send a chat transcript to the visitor when a conversation ends.

Domain logic lives here in `chat` (it knows conversations/messages); delivery goes
through the standalone `mailer` app. `chat` depends on `mailer`, never the reverse.

Synchronous — the async consumer calls it via `sync_to_async`.
"""

import logging

from django.template.loader import render_to_string
from django.utils import timezone

from mailer import service as mailer

from chat.models import Conversation, Message

logger = logging.getLogger(__name__)


def send_transcript(conversation_id) -> bool:
    """Email the visitor their transcript. Returns True iff an email was sent.

    No-op (returns False) when Resend isn't configured, the site hasn't opted in, or
    the visitor left no email.
    """
    if not mailer.enabled():
        return False
    conv = (
        Conversation.objects.select_related("site", "visitor")
        .filter(id=conversation_id)
        .first()
    )
    if conv is None or not conv.site.transcript_enabled or not conv.visitor.email:
        return False

    subject = f"Your chat transcript with {conv.site.name}"
    return mailer.send_email(
        conv.visitor.email, subject, _render_text(conv), html=_render_html(conv)
    )


def _rows(conv) -> list:
    """Message rows shared by the text and HTML renderers."""
    site_name = conv.site.name
    who = {Message.VISITOR: (conv.visitor.name or "You"), Message.OPERATOR: site_name}
    return [
        {
            "role": m.sender_role,
            "who": who.get(m.sender_role, m.sender_role),
            "time": timezone.localtime(m.created_at).strftime("%b %d, %H:%M"),
            "body": m.body,
        }
        for m in conv.messages.all()
    ]


def _render_text(conv) -> str:
    lines = [f"Your conversation with {conv.site.name}", ""]
    for r in _rows(conv):
        lines.append(f"[{r['time']}] {r['who']}: {r['body']}")
    lines += ["", "Thanks for chatting with us!"]
    return "\n".join(lines)


def _render_html(conv) -> str:
    return render_to_string(
        "email/transcript.html",
        {
            "site_name": conv.site.name,
            "color": conv.site.color,
            "operator_role": Message.OPERATOR,
            "messages": _rows(conv),
        },
    )
