from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Article,
    Favorite,
    NewsFeedback,
    NewsPreference,
    NewsSource,
    NewsFeedback,
    SupportRequest,
    Topic,
)


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "language",
        "is_active",
        "display_order",
    ]

    list_editable = [
        "is_active",
        "display_order",
    ]

    search_fields = [
        "name",
    ]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "display_order",
        "is_active",
    ]

    list_editable = [
        "display_order",
        "is_active",
    ]


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title_ja",
        "source",
        "published_at",
        "is_featured",
    ]

    list_filter = [
        "source",
        "topics",
        "is_featured",
    ]

    search_fields = [
        "title_ja",
        "title_original",
    ]

    filter_horizontal = [
        "topics",
    ]


admin.site.register(Favorite)
admin.site.register(NewsPreference)

@admin.register(NewsFeedback)
class NewsFeedbackAdmin(
    admin.ModelAdmin
):

    list_display = [
        "read_status",
        "created_at",
        "short_message",
    ]

    list_filter = [
        "is_read",
        "created_at",
    ]

    search_fields = [
        "message",
    ]

    ordering = [
        "-created_at",
    ]


    @admin.display(
        description="状態",
        ordering="is_read",
    )
    def read_status(
        self,
        obj,
    ):

        if obj.is_read:

            return format_html(
                '<span style="color:#777;">'
                "確認済み"
                "</span>"
            )

        return format_html(
            '<strong style="color:#c62828;">'
            "● 未確認"
            "</strong>"
        )


    @admin.display(
        description="コメント",
    )
    def short_message(
        self,
        obj,
    ):

        if len(obj.message) <= 80:
            return obj.message

        return (
            obj.message[:80]
            + "…"
        )

@admin.register(SupportRequest)
class SupportRequestAdmin(
    admin.ModelAdmin
):

    list_display = [
        "status_display",
        "created_at",
        "method",
        "bank_country",
        "name",
        "email",
    ]

    list_filter = [
        "is_read",
        "method",
        "bank_country",
        "created_at",
    ]

    search_fields = [
        "name",
        "email",
        "message",
    ]

    readonly_fields = [
        "method",
        "bank_country",
        "name",
        "email",
        "message",
        "created_at",
    ]

    ordering = [
        "-created_at",
    ]


    @admin.display(
        description="確認",
        ordering="is_read",
    )
    def status_display(
        self,
        obj,
    ):

        if obj.is_read:

            return format_html(
                '<span style="color:#777;">'
                "確認済み"
                "</span>"
            )

        return format_html(
            '<strong style="color:#c62828;">'
            "● 未確認"
            "</strong>"
        )