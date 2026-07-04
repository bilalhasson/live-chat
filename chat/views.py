"""Public (unauthenticated) views: the demo page and the widget's static + config."""

from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render

from chat.models import Site

_LOADER_PATH = Path(settings.BASE_DIR) / "static" / "widget" / "loader.js"


def demo(request):
    """A stand-in 'host site' that embeds the widget via a single script tag."""
    site = Site.objects.first()
    return render(request, "demo.html", {"site_key": site.public_key if site else ""})


def healthz(request):
    """Cheap liveness probe for Railway."""
    return HttpResponse("ok", content_type="text/plain")


def widget_js(request):
    """
    Serve the widget loader with a permissive CORS header and correct content-type.

    Script tags don't strictly require CORS to load, but serving it explicitly
    keeps the embedding story clean. In production WhiteNoise also serves it at
    /static/widget/loader.js.
    """
    js = _LOADER_PATH.read_text(encoding="utf-8")
    response = HttpResponse(js, content_type="application/javascript; charset=utf-8")
    response["Access-Control-Allow-Origin"] = "*"
    response["Cache-Control"] = "public, max-age=300"
    return response


def widget_config(request, site_key):
    """Per-site widget appearance, fetched cross-origin by the loader at load time."""
    site = Site.objects.filter(public_key=site_key).first()
    if site is None:
        raise Http404("unknown site")
    response = JsonResponse(site.config())
    response["Access-Control-Allow-Origin"] = "*"
    response["Cache-Control"] = "public, max-age=60"
    return response
