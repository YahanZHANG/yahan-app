from django.contrib import admin

from .models import UsageEvent


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