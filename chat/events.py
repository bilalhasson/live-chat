"""
Single source of truth for the WebSocket protocol.

Every message "type" the app speaks — both the channel-layer `group_send` event
types and the JSON types sent to browsers — is named here once, with a small builder
for each payload. Consumers import these instead of hand-writing dict literals, so
the protocol can't drift between producer and handler (and the frontend has one
place to mirror).

Naming:
  * Channel-layer event types are dotted (e.g. "chat.message"); Channels maps them
    to a handler method by replacing "." with "_" (-> `chat_message`).
  * Outbound client types are the flat strings the browser switches on.
"""

# --- roles ---
VISITOR = "visitor"
OPERATOR = "operator"

# --- channel-layer event types (group_send "type") ---
CHAT_MESSAGE = "chat.message"
CONVERSATION_UPDATE = "conversation.update"
TYPING = "typing.event"
PRESENCE = "presence.event"

# --- outbound client message types (JSON "type" to the browser) ---
C_WELCOME = "welcome"
C_HISTORY = "history"
C_MESSAGE = "message"
C_CONVERSATIONS = "conversations"
C_CONVERSATION_UPDATE = "conversation_update"
C_TYPING = "typing"
C_PRESENCE = "presence"

# --- inbound client actions ---
A_OPEN = "open"
A_MESSAGE = "message"
A_TYPING = "typing"

# presence scopes
SCOPE_OPERATOR = "operator"
SCOPE_VISITOR = "visitor"


# --- channel-layer event builders (passed to group_send) ---
def chat_message(message: dict) -> dict:
    return {"type": CHAT_MESSAGE, "message": message}


def conversation_update(conversation: dict) -> dict:
    return {"type": CONVERSATION_UPDATE, "conversation": conversation}


def typing(conversation_id, role: str, is_typing: bool) -> dict:
    return {"type": TYPING, "conversation_id": conversation_id, "role": role, "typing": is_typing}


def presence(scope: str, online: bool, conversation_id=None) -> dict:
    return {"type": PRESENCE, "scope": scope, "online": online, "conversation_id": conversation_id}


# --- outbound client payload builders (json.dumps'd and sent to the browser) ---
def client_welcome(token: str, conversation_id) -> dict:
    return {"type": C_WELCOME, "token": token, "conversation_id": conversation_id}


def client_history(messages: list, conversation_id=None) -> dict:
    return {"type": C_HISTORY, "conversation_id": conversation_id, "messages": messages}


def client_message(message: dict) -> dict:
    return {"type": C_MESSAGE, "message": message}


def client_conversations(conversations: list) -> dict:
    return {"type": C_CONVERSATIONS, "conversations": conversations}


def client_conversation_update(conversation: dict) -> dict:
    return {"type": C_CONVERSATION_UPDATE, "conversation": conversation}


def client_typing(conversation_id, role: str, is_typing: bool) -> dict:
    return {"type": C_TYPING, "conversation_id": conversation_id, "role": role, "typing": is_typing}


def client_presence(scope: str, online: bool, conversation_id=None) -> dict:
    return {"type": C_PRESENCE, "scope": scope, "online": online, "conversation_id": conversation_id}
