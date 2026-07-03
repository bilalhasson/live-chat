"""
ASGI entrypoint.

ProtocolTypeRouter sends plain HTTP to Django and `websocket` connections to
Channels. WebSocket connections pass through AuthMiddlewareStack, which reads the
session cookie into scope["user"]:
  * Operators connect same-origin from the dashboard -> authenticated user.
  * Visitors connect cross-origin from any host page -> AnonymousUser (no cookie).
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialise Django (populates apps) before importing anything that touches models.
django_asgi_app = get_asgi_application()

from chat.routing import websocket_urlpatterns  # noqa: E402  (import after app setup)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Phase 1: no origin validation yet — visitors connect cross-origin.
        # Phase 2 wraps this in a per-Site origin validator.
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
