from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

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


# =========================================================
# ユーザーの一覧: 分析画面にアクセスの記録を出すかどうかを、ここで選べるようにする
# =========================================================

class AnalyticsShownFilter(admin.SimpleListFilter):

    title = "分析に出す"
    parameter_name = "analytics"

    def lookups(self, request, model_admin):
        return [("yes", "出す"), ("no", "出さない")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(analytics_exclusion__isnull=True)
        if self.value() == "no":
            return queryset.filter(analytics_exclusion__isnull=False)
        return queryset


admin.site.unregister(User)


@admin.register(User)
class YappUserAdmin(UserAdmin):

    list_display = [
        "username",
        "email",
        "is_active",
        "analytics_shown",
        "is_staff",
        "last_login",
        "date_joined",
    ]

    list_filter = [AnalyticsShownFilter, "is_active", "is_staff", "is_superuser"]

    actions = ["show_in_analytics", "hide_from_analytics"]

    @admin.display(description="分析に出す", boolean=True)
    def analytics_shown(self, obj):
        return not hasattr(obj, "analytics_exclusion")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("analytics_exclusion")

    @admin.action(description="選んだ人のアクセスを分析に出す")
    def show_in_analytics(self, request, queryset):
        deleted, _ = AnalyticsExclusion.objects.filter(user__in=queryset).delete()
        self.message_user(request, f"{deleted}人を分析に出すようにしました。")

    @admin.action(description="選んだ人のアクセスを分析から外す（自分や家族の確認用など）")
    def hide_from_analytics(self, request, queryset):
        count = 0
        for user in queryset:
            _, created = AnalyticsExclusion.objects.get_or_create(user=user)
            count += created
        self.message_user(request, f"{count}人を分析から外しました。")
