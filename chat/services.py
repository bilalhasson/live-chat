"""
Async data-access layer for the chat consumers.

Django's ORM is synchronous; the consumers are async. Every DB touch is wrapped in
`database_sync_to_async` here and returns plain dicts / primitives (or already-loaded
model instances), so the consumers never run a query in async context themselves.
"""

from channels.db import database_sync_to_async
from django.db.models import F

from chat.models import Conversation, Message, Site, Visitor
from chat.serializers import serialize_conversation, serialize_message


@database_sync_to_async
def get_site(public_key: str):
    return Site.objects.filter(public_key=public_key).first() if public_key else None


@database_sync_to_async
def get_or_create_visitor(site: Site, token: str) -> Visitor:
    if token:
        existing = Visitor.objects.filter(site=site, token=token).first()
        if existing:
            return existing
    return Visitor.objects.create(site=site)


@database_sync_to_async
def get_or_create_conversation(site: Site, visitor: Visitor) -> Conversation:
    conv = Conversation.objects.filter(visitor=visitor).order_by("-created_at").first()
    return conv or Conversation.objects.create(site=site, visitor=visitor)


@database_sync_to_async
def save_message(conversation_id, role: str, body: str) -> dict:
    msg = Message.objects.create(conversation_id=conversation_id, sender_role=role, body=body)
    Conversation.objects.filter(id=conversation_id).update(last_message_at=msg.created_at)
    return serialize_message(msg)


@database_sync_to_async
def load_history(conversation_id) -> list:
    return [serialize_message(m) for m in Message.objects.filter(conversation_id=conversation_id)]


@database_sync_to_async
def sites_for_user(user_id) -> list:
    return list(Site.objects.filter(owner_id=user_id).values_list("id", flat=True))


@database_sync_to_async
def conversations_for_sites(site_ids) -> list:
    convs = (
        Conversation.objects.filter(site_id__in=site_ids)
        .select_related("visitor", "site")
        .order_by(F("last_message_at").desc(nulls_last=True), "-id")
    )
    return [serialize_conversation(c, c.messages.last()) for c in convs]


@database_sync_to_async
def conversation_summary(conversation_id) -> dict:
    conv = Conversation.objects.select_related("visitor", "site").get(id=conversation_id)
    return serialize_conversation(conv, conv.messages.last())


@database_sync_to_async
def canned_for_site(site_id) -> list:
    from chat.models import CannedResponse
    return list(
        CannedResponse.objects.filter(site_id=site_id).values("id", "title", "body")
    )


@database_sync_to_async
def ai_config_for_conversation(conversation_id):
    """(site_name, ai_tone, ai_context, ai_enabled) for the AI suggestion prompt."""
    conv = Conversation.objects.select_related("site").get(id=conversation_id)
    s = conv.site
    return s.name, s.ai_tone, s.ai_context, s.ai_enabled


@database_sync_to_async
def conv_site_id(conversation_id, allowed_site_ids):
    """Return the conversation's site_id iff it belongs to an allowed site, else None."""
    return (
        Conversation.objects.filter(id=conversation_id, site_id__in=allowed_site_ids)
        .values_list("site_id", flat=True)
        .first()
    )
