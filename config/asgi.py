"""
ASGI entrypoint.

The key difference from a standard WSGI Django app: this is a ProtocolTypeRouter
that sends plain HTTP to Django and `websocket` connections to Channels.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialise Django (populates apps) before importing anything that touches models.
django_asgi_app = get_asgi_application()

from chat.routing import websocket_urlpatterns  # noqa: E402  (import after app setup)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Phase 0: no origin validation — the widget connects from arbitrary host
        # pages. Phase 2 wraps this in a per-Site origin validator.
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
