from django.contrib import admin

from chat.models import Conversation, Message, Site, Visitor


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "public_key", "created_at")
    readonly_fields = ("public_key",)


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("token", "site", "created_at")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "site", "visitor", "last_message_at", "created_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender_role", "body", "created_at")
    list_filter = ("sender_role",)
