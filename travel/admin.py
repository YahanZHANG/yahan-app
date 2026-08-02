from django.contrib import admin

from .models import (
    BabyLog,
    Expense,
    ExpenseShare,
    FamilyStatus,
    ImportantNotice,
    MeetingNote,
    MilkLog,
    PoopLog,
    Schedule,
    SharedLocation,
    SleepLog,
    Task,
    UserProfile,
)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "start_at",
        "location",
        "is_important",
    )

    list_filter = (
        "is_important",
        "start_at",
    )

    search_fields = (
        "title",
        "location",
        "note",
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "assigned_to",
        "due_at",
        "priority",
        "is_completed",
    )

    list_filter = (
        "priority",
        "is_completed",
    )

    search_fields = (
        "title",
        "assigned_to",
        "note",
    )

    list_editable = (
        "is_completed",
    )


@admin.register(BabyLog)
class BabyLogAdmin(admin.ModelAdmin):
    list_display = (
        "log_type",
        "recorded_at",
        "amount",
        "unit",
    )

    list_filter = (
        "log_type",
        "recorded_at",
    )

    search_fields = (
        "note",
    )

@admin.register(FamilyStatus)
class FamilyStatusAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "location_name",
        "updated_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "user__username",
        "user__first_name",
        "location_name",
        "message",
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "has_photo",
        "updated_at",
    )

    search_fields = (
        "user__username",
        "user__first_name",
    )

    @admin.display(
        boolean=True,
        description="写真あり",
    )
    def has_photo(self, obj):
        return bool(obj.photo)

@admin.register(ImportantNotice)
class ImportantNoticeAdmin(admin.ModelAdmin):
    list_display = (
        "message_preview",
        "is_active",
        "updated_by",
        "updated_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "message",
    )

    readonly_fields = (
        "updated_at",
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        obj.updated_by = request.user
        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @admin.display(
        description="内容",
    )
    def message_preview(self, obj):
        return obj.message[:40]

class ExpenseShareInline(admin.TabularInline):
    model = ExpenseShare
    extra = 4
    min_num = 1

    fields = (
        "user",
        "amount",
    )


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "total_amount",
        "currency",
        "paid_by",
        "paid_at",
        "category",
    )

    list_filter = (
        "currency",
        "category",
        "paid_by",
    )

    search_fields = (
        "title",
        "note",
        "paid_by__username",
        "paid_by__first_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = (
        ExpenseShareInline,
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.created_by:
            obj.created_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )


@admin.register(ExpenseShare)
class ExpenseShareAdmin(admin.ModelAdmin):
    list_display = (
        "expense",
        "user",
        "amount",
    )

    list_filter = (
        "user",
    )

    search_fields = (
        "expense__title",
        "user__username",
        "user__first_name",
    )