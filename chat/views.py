from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from chat.models import Site

_LOADER_PATH = Path(settings.BASE_DIR) / "static" / "widget" / "loader.js"


def demo(request):
    """A stand-in 'host site' that embeds the widget via a single script tag."""
    site = Site.objects.first()
    return render(request, "demo.html", {"site_key": site.public_key if site else ""})


@login_required
def operator_dashboard(request):
    """The operator's live inbox: conversation list + thread + reply box."""
    return render(request, "operator.html")


def healthz(request):
    """Cheap liveness probe for Railway."""
    return HttpResponse("ok", content_type="text/plain")


def widget_js(request):
    """
    Serve the widget loader with a permissive CORS header and correct content-type.

    Script tags don't strictly require CORS to load, but serving it explicitly
    keeps the embedding story clean and forward-compatible with fetch/XHR use.
    In production WhiteNoise also serves it at /static/widget/loader.js.
    """
    js = _LOADER_PATH.read_text(encoding="utf-8")
    response = HttpResponse(js, content_type="application/javascript; charset=utf-8")
    response["Access-Control-Allow-Origin"] = "*"
    response["Cache-Control"] = "public, max-age=300"
    return response
