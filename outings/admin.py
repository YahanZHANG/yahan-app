
from django.contrib import admin

from .models import (
    Event,
    EventCategory,
    EventLocation,
    EventOccurrence,
    EventSource,
    EventTag,
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
