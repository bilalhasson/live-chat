"""
Phase 0 walking-skeleton consumer.

`EchoConsumer` joins a single Redis-backed group and re-broadcasts every message
to the whole group. Broadcasting (rather than replying on the one socket) is what
proves the Redis channel layer works: type in one browser tab and it appears in
every other connected tab, because the message round-trips through Redis.

There is deliberately NO persistence, auth, or per-conversation routing here —
that arrives in Phase 1.
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer

GROUP_NAME = "echo"


class EchoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()
        # Direct message to just this socket — confirms the connection is open.
        await self.send(text_data=json.dumps({"type": "system", "text": "connected"}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            payload = {"message": text_data}

        text = (payload.get("message") or "").strip()
        if not text:
            return

        # Fan out to everyone in the group via Redis.
        await self.channel_layer.group_send(
            GROUP_NAME,
            {"type": "echo.message", "text": text, "sender": self.channel_name},
        )

    async def echo_message(self, event):
        # Called on every consumer in the group when group_send fires.
        await self.send(
            text_data=json.dumps(
                {
                    "type": "echo",
                    "text": event["text"],
                    "self": event["sender"] == self.channel_name,
                }
            )
        )
