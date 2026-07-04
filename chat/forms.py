"""Forms for signup and site management."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from chat.models import Site


class SignupForm(UserCreationForm):
    # Email is optional — collect the minimum (data minimisation).
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ("name", "allowed_domain", "color", "position", "greeting")
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
            "allowed_domain": forms.TextInput(attrs={"placeholder": "example.com (blank = any origin)"}),
        }
        help_texts = {
            "allowed_domain": "Lock the widget to this domain (and subdomains). Leave blank to allow any origin.",
        }
