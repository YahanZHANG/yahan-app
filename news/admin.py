from django.contrib import admin

from .models import (
    Article,
    Favorite,
    NewsFeedback,
    NewsPreference,
    NewsSource,
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
class NewsFeedbackAdmin(admin.ModelAdmin):

    list_display = (
        "created_at",
        "short_message",
        "is_read",
    )

    list_filter = (
        "is_read",
        "created_at",
    )

    search_fields = (
        "message",
    )

    readonly_fields = (
        "message",
        "created_at",
    )

    ordering = (
        "-created_at",
    )

    @admin.display(
        description="コメント",
    )
    def short_message(self, obj):

        if len(obj.message) > 80:
            return f"{obj.message[:80]}…"

        return obj.message