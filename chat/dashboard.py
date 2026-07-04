"""
Authenticated dashboard views: signup + self-serve site management + the inbox.

Ownership is enforced on every site view via get_object_or_404(..., owner=request.user),
so a user can only ever see or touch their own sites (no IDOR).
"""

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from chat.forms import CannedResponseForm, SignupForm, SiteForm
from chat.models import CannedResponse, Site


def signup(request):
    if request.user.is_authenticated:
        return redirect("sites")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("sites")
    return render(request, "dashboard/signup.html", {"form": form})


@login_required
def sites(request):
    """List the user's sites and create new ones."""
    form = SiteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        site = form.save(commit=False)
        site.owner = request.user
        site.save()
        return redirect("site_detail", pk=site.pk)
    return render(request, "dashboard/sites.html", {
        "form": form,
        "sites": request.user.sites.order_by("-created_at"),
    })


@login_required
def site_detail(request, pk):
    """Edit one site's settings and show its embed snippet."""
    site = get_object_or_404(Site, pk=pk, owner=request.user)
    form = SiteForm(request.POST or None, instance=site)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("site_detail", pk=site.pk)
    snippet = (
        f'<script src="{request.scheme}://{request.get_host()}/widget.js" '
        f'data-site-key="{site.public_key}"></script>'
    )
    return render(request, "dashboard/site_detail.html", {
        "site": site,
        "form": form,
        "snippet": snippet,
        "canned": site.canned_responses.all(),
        "canned_form": CannedResponseForm(),
    })


@login_required
@require_POST
def site_delete(request, pk):
    get_object_or_404(Site, pk=pk, owner=request.user).delete()
    return redirect("sites")


@login_required
@require_POST
def canned_create(request, pk):
    site = get_object_or_404(Site, pk=pk, owner=request.user)
    form = CannedResponseForm(request.POST)
    if form.is_valid():
        canned = form.save(commit=False)
        canned.site = site
        canned.save()
    return redirect("site_detail", pk=site.pk)


@login_required
@require_POST
def canned_update(request, pk, cid):
    canned = get_object_or_404(CannedResponse, pk=cid, site_id=pk, site__owner=request.user)
    form = CannedResponseForm(request.POST, instance=canned)
    if form.is_valid():
        form.save()
    return redirect("site_detail", pk=pk)


@login_required
@require_POST
def canned_delete(request, pk, cid):
    get_object_or_404(CannedResponse, pk=cid, site_id=pk, site__owner=request.user).delete()
    return redirect("site_detail", pk=pk)


@login_required
def inbox(request):
    """The operator's live inbox (conversation list + thread + reply box)."""
    return render(request, "operator.html")
