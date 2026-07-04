"""
WebSocket consumers — the transport/protocol layer only.

Delegates everything else: DB access -> `chat.services`, protocol payloads ->
`chat.events`, group names -> `chat.groups`, ephemeral presence -> `chat.presence`,
origin checks -> `chat.security`.

Routing model
-------------
  * conv_<id>            — one conversation; the visitor + any operator viewing it.
                           Live messages and typing.
  * site_<id>_operators  — every connected operator dashboard for a site.
                           Conversation-list events + visitor presence.
  * site_<id>_visitors   — every connected visitor for a site. Operator presence.

VisitorConsumer joins its conv group + its site's visitor group. OperatorConsumer
sits in its site ops group(s) and dynamically joins/leaves one conv group as it opens
threads (the "single socket" design).

Presence and typing are ephemeral — broadcast over the channel layer, never persisted.
"""

import json
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from chat import ai, events, presence, security, services, transcripts
from chat.groups import conversation_group, site_operators_group, site_visitors_group
from chat.models import Message


class VisitorConsumer(AsyncWebsocketConsumer):
    role = events.VISITOR

    async def connect(self):
        qs = parse_qs(self.scope["query_string"].decode())
        site_key = (qs.get("site") or [""])[0]
        token = (qs.get("token") or [""])[0]
        page = (qs.get("page") or [""])[0]

        self.site = await services.get_site(site_key)
        if self.site is None:
            await self.close(code=4004)  # unknown site key
            return
        if not security.origin_allowed_for_site(self.scope, self.site.allowed_domain):
            await self.close(code=4403)  # origin not allowed for this site
            return

        self.visitor = await services.get_or_create_visitor(self.site, token)
        self.conversation = await services.get_or_create_conversation(self.site, self.visitor)
        self.group = conversation_group(self.conversation.id)
        self.visitors_group = site_visitors_group(self.site.id)
        self.identified = bool(self.visitor.email)
        if page:
            await services.set_conversation_page(self.conversation.id, page)

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(self.visitors_group, self.channel_name)
        await self.accept()

        # Register presence + let operators see this visitor is live.
        await presence.visitor_join(self.site.id, self.conversation.id)
        await self.channel_layer.group_send(
            site_operators_group(self.site.id),
            events.presence(events.SCOPE_VISITOR, True, self.conversation.id),
        )

        await self.send(text_data=json.dumps(
            events.client_welcome(self.visitor.token, self.conversation.id, self.identified)
        ))
        await self.send(text_data=json.dumps(
            events.client_history(await services.load_history(self.conversation.id))
        ))
        # Tell the visitor whether an operator is currently available.
        online = await presence.is_operator_online(self.site.id)
        await self.send(text_data=json.dumps(events.client_presence(events.SCOPE_OPERATOR, online)))

    async def disconnect(self, code):
        if not hasattr(self, "group"):
            return
        await self.channel_layer.group_discard(self.group, self.channel_name)
        await self.channel_layer.group_discard(self.visitors_group, self.channel_name)
        await presence.visitor_leave(self.site.id, self.conversation.id)
        await self.channel_layer.group_send(
            site_operators_group(self.site.id),
            events.presence(events.SCOPE_VISITOR, False, self.conversation.id),
        )

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return

        action = data.get("action")
        if action == events.A_TYPING:
            await self.channel_layer.group_send(
                self.group, events.typing(self.conversation.id, self.role, bool(data.get("typing")))
            )
            return
        if action == events.A_IDENTIFY:
            await self._identify(data.get("name", ""), data.get("email", ""))
            return

        body = (data.get("body") or data.get("message") or "").strip()
        if not body:
            return
        # Pre-chat gate: block messages until the visitor has identified (no bypass).
        if self.site.pre_chat_enabled and not self.identified:
            return
        message = await services.save_message(self.conversation.id, Message.VISITOR, body)
        await self.channel_layer.group_send(self.group, events.chat_message(message))
        await self.channel_layer.group_send(
            site_operators_group(self.site.id),
            events.conversation_update(await services.conversation_summary(self.conversation.id)),
        )

    async def _identify(self, name, email):
        name = (name or "").strip()
        email = (email or "").strip()
        try:
            validate_email(email)
        except ValidationError:
            await self.send(text_data=json.dumps(events.client_identify_error("Please enter a valid email address.")))
            return
        await services.set_visitor_identity(self.visitor.id, name, email)
        self.visitor.name, self.visitor.email = name, email
        self.identified = True
        await self.send(text_data=json.dumps(events.client_identified()))
        await self.channel_layer.group_send(
            site_operators_group(self.site.id),
            events.conversation_update(await services.conversation_summary(self.conversation.id)),
        )

    # --- channel-layer event handlers ---
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(events.client_message(event["message"])))

    async def typing_event(self, event):
        if event["role"] == self.role:
            return  # never show a party its own typing
        await self.send(text_data=json.dumps(
            events.client_typing(event["conversation_id"], event["role"], event["typing"])
        ))

    async def presence_event(self, event):
        # Visitors only receive operator-availability (via the site visitors group).
        await self.send(text_data=json.dumps(
            events.client_presence(event["scope"], event["online"], event["conversation_id"])
        ))

    async def conversation_ended(self, event):
        # An operator ended this chat → show the visitor the thank-you screen.
        await self.send(text_data=json.dumps(events.client_ended()))


class OperatorConsumer(AsyncWebsocketConsumer):
    role = events.OPERATOR

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4001)  # not logged in
            return
        if not security.origin_is_own_host(self.scope):
            await self.close(code=4403)  # cross-origin operator connection
            return

        self.site_ids = await services.sites_for_user(user.id)
        if not self.site_ids:
            await self.close(code=4003)  # operator owns no sites
            return

        self.current_conv = None
        self._suggesting = False
        for sid in self.site_ids:
            await self.channel_layer.group_add(site_operators_group(sid), self.channel_name)
            count, became_online = await presence.operator_join(sid, self.channel_name)
            if became_online:
                await self.channel_layer.group_send(
                    site_visitors_group(sid), events.presence(events.SCOPE_OPERATOR, True)
                )
        await self.accept()

        await self.send(text_data=json.dumps(
            events.client_conversations(await self._conversation_list(), ai.suggestions_enabled())
        ))

    async def disconnect(self, code):
        for sid in getattr(self, "site_ids", []):
            await self.channel_layer.group_discard(site_operators_group(sid), self.channel_name)
            count, became_offline = await presence.operator_leave(sid, self.channel_name)
            if became_offline:
                await self.channel_layer.group_send(
                    site_visitors_group(sid), events.presence(events.SCOPE_OPERATOR, False)
                )
        if getattr(self, "current_conv", None):
            await self.channel_layer.group_discard(conversation_group(self.current_conv), self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return
        action = data.get("action")
        if action == events.A_OPEN:
            await self._open(data.get("conversation_id"))
        elif action == events.A_MESSAGE:
            await self._reply(data.get("conversation_id"), (data.get("body") or "").strip())
        elif action == events.A_TYPING:
            await self._typing(data.get("conversation_id"), bool(data.get("typing")))
        elif action == events.A_SUGGEST:
            await self._suggest(data.get("conversation_id"))
        elif action == events.A_END:
            await self._end(data.get("conversation_id"))

    async def _conversation_list(self) -> list:
        """Conversations for this operator's sites, tagged with live-visitor presence."""
        online = set()
        for sid in self.site_ids:
            online |= await presence.online_conversation_ids(sid)
        conversations = await services.conversations_for_sites(self.site_ids)
        for c in conversations:
            c["online"] = c["id"] in online
        return conversations

    async def _open(self, conversation_id):
        site_id = await services.conv_site_id(conversation_id, self.site_ids)
        if site_id is None:
            return  # not one of this operator's conversations
        if self.current_conv and self.current_conv != conversation_id:
            await self.channel_layer.group_discard(conversation_group(self.current_conv), self.channel_name)
        self.current_conv = conversation_id
        await self.channel_layer.group_add(conversation_group(conversation_id), self.channel_name)
        await self.send(text_data=json.dumps(
            events.client_history(await services.load_history(conversation_id), conversation_id)
        ))
        await self.send(text_data=json.dumps(
            events.client_canned(conversation_id, await services.canned_for_site(site_id))
        ))

    async def _reply(self, conversation_id, body):
        if not body:
            return
        site_id = await services.conv_site_id(conversation_id, self.site_ids)
        if site_id is None:
            return
        message = await services.save_message(conversation_id, Message.OPERATOR, body)
        await self.channel_layer.group_send(conversation_group(conversation_id), events.chat_message(message))
        await self.channel_layer.group_send(
            site_operators_group(site_id),
            events.conversation_update(await services.conversation_summary(conversation_id)),
        )

    async def _typing(self, conversation_id, is_typing):
        if await services.conv_site_id(conversation_id, self.site_ids) is None:
            return
        await self.channel_layer.group_send(
            conversation_group(conversation_id), events.typing(conversation_id, self.role, is_typing)
        )

    async def _end(self, conversation_id):
        site_id = await services.conv_site_id(conversation_id, self.site_ids)
        if site_id is None:
            return  # not one of this operator's conversations
        await services.end_conversation(conversation_id)
        # Thank the visitor (conv group) + drop it from every operator's inbox (site ops).
        await self.channel_layer.group_send(
            conversation_group(conversation_id), events.conversation_ended(conversation_id)
        )
        await self.channel_layer.group_send(
            site_operators_group(site_id), events.conversation_removed(conversation_id)
        )
        if self.current_conv == conversation_id:
            await self.channel_layer.group_discard(conversation_group(conversation_id), self.channel_name)
            self.current_conv = None
        # Email the visitor a transcript (after the broadcasts, so ending isn't delayed;
        # a mail failure must never break the end flow).
        try:
            await sync_to_async(transcripts.send_transcript)(conversation_id)
        except Exception:
            pass

    async def _suggest(self, conversation_id):
        # Ownership + one-in-flight-per-socket guard.
        if await services.conv_site_id(conversation_id, self.site_ids) is None or self._suggesting:
            return
        if not ai.suggestions_enabled():
            await self._send(events.client_suggestion_error(conversation_id, "AI is not configured."))
            return
        name, tone, context, ai_enabled = await services.ai_config_for_conversation(conversation_id)
        if not ai_enabled:
            await self._send(events.client_suggestion_error(conversation_id, "AI is turned off for this site."))
            return

        self._suggesting = True
        try:
            history = await services.load_history(conversation_id)
            await self._send(events.client_suggestion_start(conversation_id))
            async for delta in ai.stream_suggestion(name, tone, context, history):
                await self._send(events.client_suggestion_delta(conversation_id, delta))
            await self._send(events.client_suggestion_end(conversation_id))
        except Exception:
            await self._send(events.client_suggestion_error(conversation_id, "Couldn't draft a reply. Try again."))
        finally:
            self._suggesting = False

    async def _send(self, payload: dict):
        await self.send(text_data=json.dumps(payload))

    # --- channel-layer event handlers ---
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(events.client_message(event["message"])))

    async def conversation_update(self, event):
        await self.send(text_data=json.dumps(events.client_conversation_update(event["conversation"])))

    async def typing_event(self, event):
        if event["role"] == self.role:
            return  # never show a party its own typing
        await self.send(text_data=json.dumps(
            events.client_typing(event["conversation_id"], event["role"], event["typing"])
        ))

    async def presence_event(self, event):
        # Operators only receive visitor presence (via the site operators group).
        await self.send(text_data=json.dumps(
            events.client_presence(event["scope"], event["online"], event["conversation_id"])
        ))

    async def conversation_ended(self, event):
        # No-op: an operator viewing the ended conv is also in its group, but removal is
        # driven by the site-ops `conversation_removed` event below. Handler must exist.
        pass

    async def conversation_removed(self, event):
        await self.send(text_data=json.dumps(
            events.client_conversation_removed(event["conversation_id"])
        ))
