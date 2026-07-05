"""
Stage realistic demo data for screenshots (LOCAL ONLY).

Builds a polished, deterministic scene on top of `seed_demo`'s operator + first site:
a configured site, a few canned responses, and three named conversations (one rich
"hero" thread plus two shorter ones) so the operator inbox and the embedded widget look
populated rather than empty.

Guarded on DEBUG — refuses to run against a production database. Idempotent: it deletes
its own previously-seeded visitors (by known token) and recreates them, so re-running
gives the same clean scene.

Prints a `SCREENSHOT_SEED {...}` JSON line so the capture script can read the site's
public_key and the hero visitor's token (used to preload the widget via localStorage).
"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from chat.models import CannedResponse, Conversation, Message, Site, Visitor

# Stable tokens so re-runs replace rather than duplicate.
HERO_TOKEN = "shots-priya"
TOKENS = [HERO_TOKEN, "shots-marcus", "shots-sofia"]

CANNED = [
    ("Shipping", "We ship across the EU in 3–5 working days, with tracking on every order."),
    ("Returns", "You can return any item within 30 days for a full refund — no questions asked."),
    ("Opening hours", "Our team is online Monday–Friday, 9am–6pm GMT."),
]

# (name, email, page_url, [(role, body), ...], minutes_ago_of_last_message)
CONVERSATIONS = [
    (
        "Priya Nair", "priya@example.com", "https://acme.example.com/pricing",
        [
            ("visitor", "Hi! Do you ship to Ireland?"),
            ("operator", "Hi Priya! 👋 Yes — we ship right across the EU, including Ireland."),
            ("visitor", "Great. How long does delivery usually take?"),
            ("operator", "Standard EU delivery is 3–5 working days, and you'll get tracking the moment it's dispatched."),
            ("visitor", "Perfect. Can I still change the delivery address after ordering?"),
            ("operator", "Absolutely — just reply here with your order number and the new address and I'll update it for you."),
        ],
        2,
    ),
    (
        "Marcus Lee", "marcus@example.com", "https://acme.example.com/",
        [
            ("visitor", "Is the summer sale still on?"),
            ("operator", "It is! 20% off everything until Sunday 🎉"),
        ],
        18,
    ),
    (
        "Sofia Almeida", "sofia@example.com", "https://acme.example.com/products/tote",
        [
            ("visitor", "Do you have the canvas tote in size M?"),
        ],
        41,
    ),
]


class Command(BaseCommand):
    help = "Stage realistic demo data for screenshots (local/DEBUG only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_screenshots refuses to run with DEBUG off — it is a local-only "
                "screenshot fixture and must never touch a production database."
            )

        site = Site.objects.order_by("id").first()
        if site is None:
            raise CommandError("No Site found — run `manage.py seed_demo` first.")

        # Configure the site for a clean widget presentation.
        Site.objects.filter(pk=site.pk).update(
            color="#2563eb",
            greeting="Hi! 👋 How can we help?",
            pre_chat_enabled=False,   # open straight into the conversation
            ai_enabled=True,
            ai_tone="Warm, concise, and friendly; use the customer's first name.",
            ai_context="Acme is a small EU e-commerce store selling bags and accessories. "
                       "Free EU shipping over €50, 30-day returns, summer sale 20% off until Sunday.",
            feedback_enabled=True,
        )

        # Canned responses (idempotent by title).
        for title, body in CANNED:
            CannedResponse.objects.update_or_create(site=site, title=title, defaults={"body": body})

        # Fresh slate for our seeded visitors (cascades to conversations + messages).
        Visitor.objects.filter(site=site, token__in=TOKENS).delete()

        now = timezone.now()
        for token, (name, email, page_url, messages, mins_ago) in zip(TOKENS, CONVERSATIONS):
            visitor = Visitor.objects.create(site=site, token=token, name=name, email=email)
            conv = Conversation.objects.create(site=site, visitor=visitor, page_url=page_url)

            # Space messages ~2 min apart, ending `mins_ago` before now.
            n = len(messages)
            created_msgs = []
            for i, (role, body) in enumerate(messages):
                m = Message.objects.create(conversation=conv, sender_role=role, body=body)
                ts = now - timezone.timedelta(minutes=mins_ago + (n - 1 - i) * 2)
                created_msgs.append((m.pk, ts))
            # created_at is auto_now_add; backdate via update() so ordering is stable.
            for pk, ts in created_msgs:
                Message.objects.filter(pk=pk).update(created_at=ts)
            last_ts = now - timezone.timedelta(minutes=mins_ago)
            Conversation.objects.filter(pk=conv.pk).update(
                created_at=now - timezone.timedelta(minutes=mins_ago + (n - 1) * 2),
                last_message_at=last_ts,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(TOKENS)} conversations + {len(CANNED)} canned responses on "
            f"'{site.name}'."
        ))
        # Machine-readable line for the capture script.
        self.stdout.write("SCREENSHOT_SEED " + json.dumps({
            "public_key": site.public_key,
            "site_name": site.name,
            "hero_token": HERO_TOKEN,
        }))
