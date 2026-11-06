"""
スイス生活の知恵袋の管理画面。

- 掲示板の設定: 公開のオン・オフ、事前アンケートからの取り込みボタン
- 質問・答え・ゆずります/本: 公開・非公開の切り替え
- 通報: 対応済みのチェック
- やりとり (ほしい・借りたい) は、トラブルのときに確認できるよう読むだけ
"""

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import path, reverse

from .models import (
    Answer,
    BoardSettings,
    Item,
    ItemRequest,
    Message,
    Question,
    Report,
    Status,
)
from .services import import_from_survey


@admin.register(BoardSettings)
class BoardSettingsAdmin(admin.ModelAdmin):

    list_display = ["__str__", "is_open", "updated_at"]
    list_editable = ["is_open"]
    list_display_links = ["__str__"]
    change_list_template = "admin/chiebukuro/boardsettings/change_list.html"

    def has_add_permission(self, request):
        return not BoardSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        BoardSettings.current()
        return super().changelist_view(request, extra_context)

    def get_urls(self):
        return [
            path("import-survey/", self.admin_site.admin_view(self.import_survey), name="chiebukuro_import_survey"),
        ] + super().get_urls()

    def import_survey(self, request):
        if request.method == "POST":
            questions, answers = import_from_survey()
            messages.success(request, f"事前アンケートから、質問 {questions} 件・答え {answers} 件を取り込みました。")
        return redirect(reverse("admin:chiebukuro_boardsettings_changelist"))


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    fields = ["body", "nickname", "status", "from_survey", "created_at"]
    readonly_fields = ["from_survey", "created_at"]
    show_change_link = True


def set_status(modeladmin, request, queryset, status, label):
    count = queryset.update(status=status)
    modeladmin.message_user(request, f"{count}件を「{label}」にしました。")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):

    list_display = ["short_body", "theme", "region", "status", "source", "nickname", "answer_count", "interest_count", "created_at"]
    list_display_links = ["short_body"]
    list_editable = ["theme", "region", "status"]
    list_filter = ["status", "theme", "source", "region"]
    search_fields = ["body", "nickname", "author__username"]
    readonly_fields = ["source", "author", "survey_question_id", "last_answered_at", "updated_at"]
    inlines = [AnswerInline]
    actions = ["publish", "hide"]
    list_per_page = 100

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            answers_total=Count("answers", filter=Q(answers__status=Status.PUBLISHED), distinct=True),
            interests_total=Count("interests", distinct=True),
        )

    @admin.display(description="質問")
    def short_body(self, obj):
        return obj.body if len(obj.body) <= 50 else obj.body[:50] + "…"

    @admin.display(description="答え", ordering="answers_total")
    def answer_count(self, obj):
        return obj.answers_total

    @admin.display(description="知りたい", ordering="interests_total")
    def interest_count(self, obj):
        return obj.interests_total + obj.survey_interest_count

    @admin.action(description="公開する")
    def publish(self, request, queryset):
        set_status(self, request, queryset, Status.PUBLISHED, "公開")

    @admin.action(description="非公開にする")
    def hide(self, request, queryset):
        set_status(self, request, queryset, Status.HIDDEN, "非公開")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):

    list_display = ["short_body", "question", "nickname", "status", "from_survey", "created_at"]
    list_editable = ["status"]
    list_filter = ["status", "from_survey"]
    search_fields = ["body", "nickname", "author__username"]
    readonly_fields = ["question", "author", "from_survey"]
    actions = ["publish", "hide"]
    list_per_page = 100

    @admin.display(description="答え")
    def short_body(self, obj):
        return obj.body if len(obj.body) <= 50 else obj.body[:50] + "…"

    @admin.action(description="公開する")
    def publish(self, request, queryset):
        set_status(self, request, queryset, Status.PUBLISHED, "公開")

    @admin.action(description="非公開にする")
    def hide(self, request, queryset):
        set_status(self, request, queryset, Status.HIDDEN, "非公開")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):

    list_display = ["title", "kind", "state", "status", "region", "nickname", "request_count", "created_at"]
    list_editable = ["status"]
    list_filter = ["kind", "state", "status", "region"]
    search_fields = ["title", "body", "nickname", "owner__username"]
    readonly_fields = ["owner"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(requests_total=Count("requests"))

    @admin.display(description="ほしい・借りたい", ordering="requests_total")
    def request_count(self, obj):
        return obj.requests_total


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ["sender", "body", "created_at"]
    readonly_fields = fields
    can_delete = False


@admin.register(ItemRequest)
class ItemRequestAdmin(admin.ModelAdmin):
    """トラブルの確認用 (読むだけ)"""

    list_display = ["item", "nickname", "is_chosen", "last_message_at"]
    list_filter = ["is_chosen"]
    search_fields = ["item__title", "nickname", "requester__username"]
    inlines = [MessageInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):

    list_display = ["created_at", "target", "target_link", "reason", "reporter", "handled"]
    list_editable = ["handled"]
    list_filter = ["handled", "target"]

    @admin.display(description="対象")
    def target_link(self, obj):
        from django.utils.html import format_html

        names = {"question": "question", "answer": "answer", "item": "item"}
        if obj.target not in names:
            return obj.target_id
        url = reverse(f"admin:chiebukuro_{names[obj.target]}_change", args=[obj.target_id])
        return format_html('<a href="{}">#{} を開く</a>', url, obj.target_id)
