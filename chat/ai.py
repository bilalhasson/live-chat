"""
Anthropic-backed suggested replies — the only place the app talks to Claude.

Kept isolated so the consumer stays transport-only. The feature is gated on
ANTHROPIC_API_KEY (absent = feature off, no client is ever constructed). The model is
env-configurable (default Haiku 4.5 — fast and cheap for a real-time suggest button).
Uses the async SDK and streams, so drafts arrive token-by-token.
"""

import os

from anthropic import AsyncAnthropic

DEFAULT_MODEL = "claude-haiku-4-5"


def suggestions_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)


def _system_prompt(site_name: str, tone: str, context: str) -> str:
    parts = [f"You are a helpful customer-support agent for {site_name}."]
    if context.strip():
        parts.append(f"About the business:\n{context.strip()}")
    if tone.strip():
        parts.append(f"Tone and voice: {tone.strip()}")
    parts.append(
        "Draft the next reply to the visitor based on the conversation so far. Be "
        "concise and genuinely helpful. Output only the reply text — no preamble, no "
        "surrounding quotes, and no sign-off unless the tone instructions ask for one."
    )
    return "\n\n".join(parts)


def _to_messages(history: list) -> list:
    """Map persisted history (visitor/operator) to Anthropic user/assistant turns."""
    messages = []
    for m in history:
        body = (m.get("body") or "").strip()
        if body:
            role = "user" if m.get("role") == "visitor" else "assistant"
            messages.append({"role": role, "content": body})
    # The Messages API must start with a user turn.
    if not messages or messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "(The conversation has just begun.)"})
    return messages


async def stream_suggestion(site_name: str, tone: str, context: str, history: list):
    """Yield the drafted reply as text deltas. Raises on API/auth errors."""
    client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY; only built when enabled
    async with client.messages.stream(
        model=_model(),
        max_tokens=300,
        system=_system_prompt(site_name, tone, context),
        messages=_to_messages(history),
    ) as stream:
        async for text in stream.text_stream:
            yield text
