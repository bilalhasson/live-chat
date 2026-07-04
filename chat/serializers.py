"""
Pure serialization: model instance -> plain dict for the wire.

No DB access here. Callers must pass already-loaded objects (select_related the
visitor, fetch the last message), which keeps these safe to call from anywhere,
including async context.
"""

from chat.models import Conversation, Message


def serialize_message(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.sender_role,
        "body": msg.body,
        "created_at": msg.created_at.isoformat(),
    }


def serialize_conversation(conv: Conversation, last_message: Message | None) -> dict:
    return {
        "id": conv.id,
        "site": conv.site.name,
        "ai": conv.site.ai_enabled,
        "visitor": conv.visitor.token[:8],
        "last_body": last_message.body if last_message else "",
        "last_role": last_message.sender_role if last_message else "",
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
    }
