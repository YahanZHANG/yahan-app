from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):

    list_display = [

        "id",

        "sender",

        "recipient",

        "short_body",

        "is_read",

        "created_at",

    ]

    list_filter = [

        "is_read",

        "created_at",

    ]

    search_fields = [

        "sender__username",

        "recipient__username",

        "body",

    ]

    readonly_fields = [

        "created_at",

    ]

    @admin.display(
        description="メッセージ"
    )
    def short_body(self, obj):

        return obj.body[:50]