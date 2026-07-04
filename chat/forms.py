"""Forms for signup and site management."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from chat.models import CannedResponse, Site


class SignupForm(UserCreationForm):
    # Email is optional — collect the minimum (data minimisation).
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = (
            "name", "allowed_domain", "color", "position", "greeting",
            "pre_chat_enabled", "transcript_enabled", "ai_enabled", "ai_tone", "ai_context",
        )
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
            "allowed_domain": forms.TextInput(attrs={"placeholder": "example.com (blank = any origin)"}),
            "ai_tone": forms.Textarea(attrs={"rows": 2, "placeholder": "e.g. Warm and casual; use the visitor's first name."}),
            "ai_context": forms.Textarea(attrs={"rows": 4, "placeholder": "What your business does, key facts, hours, policies…"}),
        }
        labels = {
            "pre_chat_enabled": "Pre-chat form",
            "transcript_enabled": "Email transcripts",
            "ai_enabled": "AI suggested replies",
            "ai_tone": "AI tone of voice",
            "ai_context": "AI business context",
        }
        help_texts = {
            "allowed_domain": "Lock the widget to this domain (and subdomains). Leave blank to allow any origin.",
            "pre_chat_enabled": "Ask visitors for their name and email before they can start chatting.",
            "transcript_enabled": "Email the visitor a transcript when a chat ends — needs their email and Resend configured.",
            "ai_context": "Grounds the AI's drafts in your business. The single biggest lever on reply quality.",
        }


class CannedResponseForm(forms.ModelForm):
    class Meta:
        model = CannedResponse
        fields = ("title", "body")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Business hours"}),
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "The saved reply text…"}),
        }
