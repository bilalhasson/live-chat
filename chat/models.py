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

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=120)
    public_key = models.CharField(max_length=64, unique=True, default=gen_key, db_index=True)
    allowed_domain = models.CharField(max_length=255, blank=True, default="")  # used for origin checks in Phase 2
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.public_key[:8]}…)"


class Visitor(models.Model):
    """An anonymous website visitor, remembered across reloads via `token`."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="visitors")
    token = models.CharField(max_length=64, unique=True, default=gen_key, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Visitor {self.token[:8]}… @ {self.site.name}"


class Conversation(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="conversations")
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

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
