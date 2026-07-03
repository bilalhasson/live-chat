"""
Phase 1 consumers: real visitor <-> operator chat over WebSockets, persisted to
Postgres and fanned out via Redis groups.

Routing model
-------------
Two kinds of Redis group:
  * conv_<id>            — one per conversation; the visitor + any operator
                           currently viewing that thread. Live message delivery.
  * site_<id>_operators  — one per site; every connected operator dashboard.
                           List-level events (new conversation / new message).

VisitorConsumer joins only its conv group. OperatorConsumer always sits in its
site ops group(s) and dynamically joins/leaves a single conv group as the operator
opens conversations (the "single socket" design).
"""

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import F

from chat.models import Conversation, Message, Site, Visitor


def conv_group(conversation_id) -> str:
    return f"conv_{conversation_id}"


def site_ops_group(site_id) -> str:
    return f"site_{site_id}_operators"


def message_to_dict(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.sender_role,
        "body": msg.body,
        "created_at": msg.created_at.isoformat(),
    }


def _summarize(conv: Conversation) -> dict:
    last = conv.messages.last()
    return {
        "id": conv.id,
        "visitor": conv.visitor.token[:8],
        "last_body": last.body if last else "",
        "last_role": last.sender_role if last else "",
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
    }


# --- Shared DB helpers (sync ORM wrapped for the async consumers) -----------

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
def save_message(conversation_id, role: str, body: str) -> Message:
    msg = Message.objects.create(conversation_id=conversation_id, sender_role=role, body=body)
    Conversation.objects.filter(id=conversation_id).update(last_message_at=msg.created_at)
    return msg


@database_sync_to_async
def load_history(conversation_id) -> list:
    return [message_to_dict(m) for m in Message.objects.filter(conversation_id=conversation_id)]


@database_sync_to_async
def sites_for_user(user_id) -> list:
    return list(Site.objects.filter(owner_id=user_id).values_list("id", flat=True))


@database_sync_to_async
def conversations_for_sites(site_ids) -> list:
    convs = (
        Conversation.objects.filter(site_id__in=site_ids)
        .select_related("visitor")
        .order_by(F("last_message_at").desc(nulls_last=True), "-id")
    )
    return [_summarize(c) for c in convs]


@database_sync_to_async
def conversation_summary(conversation_id) -> dict:
    conv = Conversation.objects.select_related("visitor").get(id=conversation_id)
    return _summarize(conv)


@database_sync_to_async
def conv_site_id(conversation_id, allowed_site_ids):
    """Return the conversation's site_id iff it belongs to an allowed site, else None."""
    return (
        Conversation.objects.filter(id=conversation_id, site_id__in=allowed_site_ids)
        .values_list("site_id", flat=True)
        .first()
    )


class VisitorConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        qs = parse_qs(self.scope["query_string"].decode())
        site_key = (qs.get("site") or [""])[0]
        token = (qs.get("token") or [""])[0]

        self.site = await get_site(site_key)
        if self.site is None:
            await self.close(code=4004)  # unknown site key
            return

        self.visitor = await get_or_create_visitor(self.site, token)
        self.conversation = await get_or_create_conversation(self.site, self.visitor)
        self.group = conv_group(self.conversation.id)

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        # Hand the client its persistent token (so reloads reuse the same visitor).
        await self.send(text_data=json.dumps({
            "type": "welcome",
            "token": self.visitor.token,
            "conversation_id": self.conversation.id,
        }))
        history = await load_history(self.conversation.id)
        await self.send(text_data=json.dumps({"type": "history", "messages": history}))

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return
        body = (data.get("body") or data.get("message") or "").strip()
        if not body:
            return

        msg = await save_message(self.conversation.id, Message.VISITOR, body)
        await self.channel_layer.group_send(
            self.group, {"type": "chat.message", "message": message_to_dict(msg)}
        )
        await self.channel_layer.group_send(
            site_ops_group(self.site.id),
            {"type": "conversation.update", "conversation": await conversation_summary(self.conversation.id)},
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", "message": event["message"]}))


class OperatorConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4001)  # not logged in
            return

        self.site_ids = await sites_for_user(user.id)
        if not self.site_ids:
            await self.close(code=4003)  # operator owns no sites
            return

        self.current_conv = None
        for sid in self.site_ids:
            await self.channel_layer.group_add(site_ops_group(sid), self.channel_name)
        await self.accept()

        convs = await conversations_for_sites(self.site_ids)
        await self.send(text_data=json.dumps({"type": "conversations", "conversations": convs}))

    async def disconnect(self, code):
        for sid in getattr(self, "site_ids", []):
            await self.channel_layer.group_discard(site_ops_group(sid), self.channel_name)
        if getattr(self, "current_conv", None):
            await self.channel_layer.group_discard(conv_group(self.current_conv), self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return
        action = data.get("action")
        if action == "open":
            await self._open(data.get("conversation_id"))
        elif action == "message":
            await self._reply(data.get("conversation_id"), (data.get("body") or "").strip())

    async def _open(self, conversation_id):
        if await conv_site_id(conversation_id, self.site_ids) is None:
            return  # not one of this operator's conversations
        if self.current_conv and self.current_conv != conversation_id:
            await self.channel_layer.group_discard(conv_group(self.current_conv), self.channel_name)
        self.current_conv = conversation_id
        await self.channel_layer.group_add(conv_group(conversation_id), self.channel_name)
        history = await load_history(conversation_id)
        await self.send(text_data=json.dumps(
            {"type": "history", "conversation_id": conversation_id, "messages": history}
        ))

    async def _reply(self, conversation_id, body):
        if not body:
            return
        site_id = await conv_site_id(conversation_id, self.site_ids)
        if site_id is None:
            return
        msg = await save_message(conversation_id, Message.OPERATOR, body)
        await self.channel_layer.group_send(
            conv_group(conversation_id), {"type": "chat.message", "message": message_to_dict(msg)}
        )
        await self.channel_layer.group_send(
            site_ops_group(site_id),
            {"type": "conversation.update", "conversation": await conversation_summary(conversation_id)},
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", "message": event["message"]}))

    async def conversation_update(self, event):
        await self.send(text_data=json.dumps(
            {"type": "conversation_update", "conversation": event["conversation"]}
        ))
