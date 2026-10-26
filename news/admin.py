from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Article,
    Favorite,
    NewsAnnouncement,
    NewsFeedback,
    NewsPreference,
    NewsPushSubscription,
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
        "life_alert",
    ]

    # AI の「暮らしのお知らせ」判定が違うときは一覧で直せる
    list_editable = [
        "life_alert",
    ]

    list_filter = [
        "life_alert",
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

@admin.register(NewsAnnouncement)
class NewsAnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        "message",
        "is_active",
        "created_at",
    ]

    list_editable = [
        "is_active",
    ]



@admin.register(NewsPushSubscription)
class NewsPushSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "frequency",
        "region_names",
        "updated_at",
    ]

    list_filter = [
        "frequency",
        "alert_regions",
    ]

    filter_horizontal = [
        "alert_regions",
    ]

    readonly_fields = [
        "endpoint",
        "p256dh",
        "auth",
        "created_at",
        "updated_at",
    ]

    def get_queryset(self, request):

        return (
            super()
            .get_queryset(request)
            .prefetch_related("alert_regions")
        )

    @admin.display(description="暮らしのお知らせの地域")
    def region_names(self, obj):

        return "、".join(
            region.name
            for region in obj.alert_regions.all()
        )
