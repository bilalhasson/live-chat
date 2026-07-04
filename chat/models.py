"""
Phase 1 data model.

Multi-tenant by design (every Conversation hangs off a Site), but Phase 1 seeds a
single Site — the self-serve "create your own site" UI is deferred to a later phase.
"""

import secrets

from django.conf import settings
from django.db import models


def gen_key() -> str:
    return secrets.token_urlsafe(24)


class Site(models.Model):
    """A tenant: one embeddable widget, identified publicly by `public_key`."""

    POSITIONS = [("bottom-right", "Bottom right"), ("bottom-left", "Bottom left")]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=120)
    public_key = models.CharField(max_length=64, unique=True, default=gen_key, db_index=True)
    allowed_domain = models.CharField(max_length=255, blank=True, default="")  # used for origin checks in Phase 2

    # Widget appearance — edited in the dashboard, served to the widget by config.json.
    color = models.CharField(max_length=7, default="#2563eb")
    position = models.CharField(max_length=16, choices=POSITIONS, default="bottom-right")
    greeting = models.CharField(max_length=200, default="Hi! How can we help?")

    # AI-assisted replies (operator-side only; never served to the widget).
    ai_enabled = models.BooleanField(default=True)
    ai_tone = models.TextField(blank=True, default="")
    ai_context = models.TextField(blank=True, default="")

    # Pre-chat form: require a name/email before the visitor can chat.
    pre_chat_enabled = models.BooleanField(default=False)

    # Email the visitor a transcript when a chat ends (needs their email + Resend).
    transcript_enabled = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.public_key[:8]}…)"

    def config(self) -> dict:
        """Public widget config (safe to expose cross-origin)."""
        return {
            "name": self.name,
            "color": self.color,
            "position": self.position,
            "greeting": self.greeting,
            "pre_chat": self.pre_chat_enabled,
        }


class Visitor(models.Model):
    """An anonymous website visitor, remembered across reloads via `token`."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="visitors")
    token = models.CharField(max_length=64, unique=True, default=gen_key, db_index=True)
    name = models.CharField(max_length=120, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Visitor {self.token[:8]}… @ {self.site.name}"


class Conversation(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="conversations")
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="conversations")
    page_url = models.CharField(max_length=500, blank=True, default="")  # host page the visitor is on
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)  # set when an operator ends the chat

    def __str__(self):
        return f"Conversation #{self.pk} ({self.visitor.token[:8]}…)"


class Message(models.Model):
    VISITOR = "visitor"
    OPERATOR = "operator"
    ROLE_CHOICES = [(VISITOR, "Visitor"), (OPERATOR, "Operator")]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.sender_role}] {self.body[:40]}"


class CannedResponse(models.Model):
    """A saved reply template an operator can insert (per Site)."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="canned_responses")
    title = models.CharField(max_length=80)  # the "/shortcut" label
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
