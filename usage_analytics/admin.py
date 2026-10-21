from django.contrib import admin

from .models import AnalyticsExclusion, PageView, UsageEvent


@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):

    list_display = [
        "user",
        "app_key",
        "accessed_at",
        "is_visit_start",
    ]

    list_filter = [
        "app_key",
        "is_visit_start",
        "accessed_at",
    ]

    search_fields = [
        "user__username",
    ]

    date_hierarchy = "accessed_at"

    readonly_fields = [
        "user",
        "app_key",
        "accessed_at",
        "is_visit_start",
    ]

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):

    list_display = ["accessed_at", "app_key", "path", "user", "source_type", "source_label", "device_type"]

    list_filter = ["app_key", "source_type", "device_type", "is_visit_start"]

    search_fields = ["path", "source_label", "user__username"]

    date_hierarchy = "accessed_at"

    ordering = ["-accessed_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AnalyticsExclusion)
class AnalyticsExclusionAdmin(admin.ModelAdmin):

    list_display = ["user", "created_at"]
