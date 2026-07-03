"""
WebSocket consumers — the transport/protocol layer only.

Business logic and DB access live in `chat.services`; group names in `chat.groups`;
wire serialization in `chat.serializers`. This module is deliberately just the two
AsyncWebsocketConsumer classes and the JSON message protocol they speak.

Routing model
-------------
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

from channels.generic.websocket import AsyncWebsocketConsumer

from chat import services
from chat.groups import conversation_group, site_operators_group
from chat.models import Message


class VisitorConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        qs = parse_qs(self.scope["query_string"].decode())
        site_key = (qs.get("site") or [""])[0]
        token = (qs.get("token") or [""])[0]

        self.site = await services.get_site(site_key)
        if self.site is None:
            await self.close(code=4004)  # unknown site key
            return

        self.visitor = await services.get_or_create_visitor(self.site, token)
        self.conversation = await services.get_or_create_conversation(self.site, self.visitor)
        self.group = conversation_group(self.conversation.id)

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        # Hand the client its persistent token (so reloads reuse the same visitor).
        await self.send(text_data=json.dumps({
            "type": "welcome",
            "token": self.visitor.token,
            "conversation_id": self.conversation.id,
        }))
        await self.send(text_data=json.dumps({
            "type": "history",
            "messages": await services.load_history(self.conversation.id),
        }))

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

        message = await services.save_message(self.conversation.id, Message.VISITOR, body)
        await self.channel_layer.group_send(self.group, {"type": "chat.message", "message": message})
        await self.channel_layer.group_send(
            site_operators_group(self.site.id),
            {"type": "conversation.update", "conversation": await services.conversation_summary(self.conversation.id)},
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", "message": event["message"]}))


class OperatorConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4001)  # not logged in
            return

        self.site_ids = await services.sites_for_user(user.id)
        if not self.site_ids:
            await self.close(code=4003)  # operator owns no sites
            return

        self.current_conv = None
        for sid in self.site_ids:
            await self.channel_layer.group_add(site_operators_group(sid), self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "conversations",
            "conversations": await services.conversations_for_sites(self.site_ids),
        }))

    async def disconnect(self, code):
        for sid in getattr(self, "site_ids", []):
            await self.channel_layer.group_discard(site_operators_group(sid), self.channel_name)
        if getattr(self, "current_conv", None):
            await self.channel_layer.group_discard(conversation_group(self.current_conv), self.channel_name)

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
        if await services.conv_site_id(conversation_id, self.site_ids) is None:
            return  # not one of this operator's conversations
        if self.current_conv and self.current_conv != conversation_id:
            await self.channel_layer.group_discard(conversation_group(self.current_conv), self.channel_name)
        self.current_conv = conversation_id
        await self.channel_layer.group_add(conversation_group(conversation_id), self.channel_name)
        await self.send(text_data=json.dumps({
            "type": "history",
            "conversation_id": conversation_id,
            "messages": await services.load_history(conversation_id),
        }))

    async def _reply(self, conversation_id, body):
        if not body:
            return
        site_id = await services.conv_site_id(conversation_id, self.site_ids)
        if site_id is None:
            return
        message = await services.save_message(conversation_id, Message.OPERATOR, body)
        await self.channel_layer.group_send(
            conversation_group(conversation_id), {"type": "chat.message", "message": message}
        )
        await self.channel_layer.group_send(
            site_operators_group(site_id),
            {"type": "conversation.update", "conversation": await services.conversation_summary(conversation_id)},
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", "message": event["message"]}))

    async def conversation_update(self, event):
        await self.send(text_data=json.dumps(
            {"type": "conversation_update", "conversation": event["conversation"]}
        ))
