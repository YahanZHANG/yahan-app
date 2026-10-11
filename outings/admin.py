
from django.contrib import admin
from django.utils import timezone

from .models import (
    Event,
    EventCategory,
    EventLocation,
    EventOccurrence,
    EventSource,
    EventTag,
    OutingsComment,
)


class EventOccurrenceInline(admin.TabularInline):
    model = EventOccurrence
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "status",
        "event_type",
        "category",
        "location",
        "language_barrier",
        "created_at",
    )

    list_filter = (
        "status",
        "event_type",
        "category",
        "language_barrier",
        "is_free",
        "source",
    )

    search_fields = (
        "title",
        "title_original",
        "summary_ja",
        "location__city",
    )

    filter_horizontal = ("tags",)

    inlines = [EventOccurrenceInline]

    readonly_fields = (
        "created_at",
        "updated_at",
        "ai_processed_at",
    )

    fieldsets = (
        (
            "基本情報",
            {
                "fields": (
                    "title",
                    "title_original",
                    "summary_ja",
                    "description_original",
                    "category",
                    "tags",
                )
            },
        ),
        (
            "開催情報",
            {
                "fields": (
                    "event_type",
                    "location",
                    "language_barrier",
                    "is_free",
                    "price_text",
                    "is_indoor",
                    "is_outdoor",
                )
            },
        ),
        (
            "リンク・収集元",
            {
                "fields": (
                    "original_url",
                    "image_url",
                    "source",
                    "external_id",
                )
            },
        ),
        (
            "公開管理",
            {
                "fields": (
                    "status",
                    "created_by",
                    "ai_processed_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(EventOccurrence)
class EventOccurrenceAdmin(admin.ModelAdmin):
    list_display = ("event", "start_at", "end_at", "is_cancelled")
    list_filter = ("is_cancelled",)


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(EventTag)
class EventTagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(EventLocation)
class EventLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "canton")
    search_fields = ("name", "city", "address")


@admin.register(EventSource)
class EventSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "last_synced_at")


# =========================================================
# Comments Admin
# =========================================================

@admin.register(OutingsComment)
class OutingsCommentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "event",
        "author",
        "comment_preview",
        "is_deleted",
        "deleted_by",
        "created_at",
    )

    list_filter = (
        "is_deleted",
        "created_at",
    )

    search_fields = (
        "body",
        "event__title",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
        "deleted_reason",
    )

    list_select_related = (
        "event",
        "author",
        "deleted_by",
    )

    ordering = ("-created_at", "-pk")

    actions = [
        "hide_comments",
        "restore_comments",
    ]

    @admin.display(description="本文")
    def comment_preview(self, obj):
        return obj.body[:80]

    @admin.action(description="選択したコメントを非表示にする")
    def hide_comments(self, request, queryset):

        queryset.filter(
            is_deleted=False
        ).update(
            is_deleted=True,
            deleted_at=timezone.now(),
            deleted_by=request.user,
            deleted_reason="Adminによる非表示",
        )

    @admin.action(description="選択したコメントを復元する")
    def restore_comments(self, request, queryset):

        queryset.update(
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            deleted_reason="",
        )
