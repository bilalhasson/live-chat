"""
Idempotent seed: ensure an operator user and a demo Site exist.

Local dev (DEBUG on): creates a superuser `admin` / `password`.
Production: set OPERATOR_USERNAME / OPERATOR_PASSWORD env vars. Without a password
and with DEBUG off, user creation is skipped (never ship a default password live).
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from chat.models import Site


class Command(BaseCommand):
    help = "Ensure an operator user and a demo Site exist."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("OPERATOR_USERNAME", "admin")
        password = os.environ.get("OPERATOR_PASSWORD") or ("password" if settings.DEBUG else None)

        user = User.objects.filter(username=username).first()
        if user is None:
            if not password:
                self.stdout.write(self.style.WARNING(
                    f"No user '{username}' and no OPERATOR_PASSWORD set (DEBUG off) — "
                    "skipping user + site seed. Set OPERATOR_PASSWORD to enable."
                ))
                return
            user = User.objects.create_superuser(username=username, email="", password=password)
            self.stdout.write(self.style.SUCCESS(f"Created operator '{username}'."))
        else:
            self.stdout.write(f"Operator '{username}' already exists — leaving password as-is.")

        site, created = Site.objects.get_or_create(owner=user, name="Demo Site")
        verb = "Created" if created else "Found"
        self.stdout.write(self.style.SUCCESS(f"{verb} 'Demo Site' — public_key: {site.public_key}"))
