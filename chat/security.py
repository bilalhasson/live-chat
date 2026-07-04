"""
WebSocket origin checks.

WebSockets aren't covered by the browser's same-origin policy or CORS, but the
browser *does* send an Origin header it cannot forge. We use it two ways:

  * Operators — only accept connections whose Origin is one of the app's own hosts
    (ALLOWED_HOSTS). Stops a malicious third-party page from opening an operator
    socket on a logged-in victim's cookies.
  * Visitors — if a Site pins an `allowed_domain`, only accept widget connections
    coming from that domain (or a subdomain). An empty `allowed_domain` allows any
    origin, which is what the demo Site uses.

Non-browser clients (no Origin header) are allowed: browsers always send Origin,
so an absent one can't be a cross-site browser attack, and such clients don't carry
a victim's cookies anyway.
"""

from urllib.parse import urlparse

from django.conf import settings


def origin_host(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"origin":
            return urlparse(value.decode()).hostname
    return None


def _matches(host: str, domain: str) -> bool:
    host, domain = host.lower(), domain.lower().lstrip(".")
    return host == domain or host.endswith("." + domain)


def origin_is_own_host(scope) -> bool:
    """True if the connection's Origin is one of the app's own hosts."""
    host = origin_host(scope)
    if host is None:
        return True  # non-browser client
    for allowed in settings.ALLOWED_HOSTS:
        if allowed == "*" or _matches(host, allowed):
            return True
    return False


def origin_allowed_for_site(scope, allowed_domain: str) -> bool:
    """True if the widget's Origin is allowed for this Site."""
    if not allowed_domain:
        return True  # Site accepts any origin (e.g. the demo Site)
    # A pinned Site requires a matching, verifiable origin. A missing or opaque
    # origin — "null" from file:// or a sandboxed iframe — can't be trusted to be
    # the pinned domain, so reject it.
    host = origin_host(scope)
    return host is not None and _matches(host, allowed_domain)
