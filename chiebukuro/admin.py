"""
スイス生活の知恵袋の管理画面。

- 掲示板の設定: 公開のオン・オフ、事前アンケートからの取り込みボタン
- 質問・答え・つぶやき・ゆずりあい・募集告知: 公開・非公開の切り替え
- 通報: 対応済みのチェック
- やりとり (2人だけのメッセージ) は、トラブルのときに確認できるよう読むだけ
"""

from datetime import timedelta

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    Answer,
    BoardSettings,
    Item,
    ItemRequest,
    Message,
    Notice,
    Poll,
    PollChoice,
    BotPost,
    Post,
    PostReply,
    Question,
    Contact,
    Report,
    Sponsor,
    Status,
)
from .services import import_from_survey


@admin.register(BoardSettings)
class BoardSettingsAdmin(admin.ModelAdmin):

    list_display = ["__str__", "is_open", "hero_season", "release_start", "release_first", "release_per_day", "release_open_first", "release_open_per_day", "queued_count", "rules_updated_at", "updated_at"]
    list_editable = ["is_open", "hero_season", "release_start", "release_first", "release_per_day", "release_open_first", "release_open_per_day"]
    readonly_fields = ["preview_key"]
    list_display_links = ["__str__"]
    change_list_template = "admin/chiebukuro/boardsettings/change_list.html"

    @admin.display(description="公開待ちの質問")
    def queued_count(self, obj):
        from .models import QUEUED

        return Question.objects.filter(status=QUEUED).count()

    def has_add_permission(self, request):
        return not BoardSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


    def get_urls(self):
        return [
            path("import-survey/", self.admin_site.admin_view(self.import_survey), name="chiebukuro_import_survey"),
            path("preview-link/", self.admin_site.admin_view(self.preview_link), name="chiebukuro_preview_link"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        settings_row = BoardSettings.current()
        link = ""
        if settings_row.preview_key:
            link = request.build_absolute_uri(reverse("chiebukuro:home")) + f"?preview={settings_row.preview_key}"
        extra_context = dict(extra_context or {}, preview_link=link)
        return super().changelist_view(request, extra_context)

    def preview_link(self, request):
        if request.method == "POST":
            BoardSettings.current().new_preview_key()
            messages.success(request, "先行公開のリンクを作りました。前のリンクは使えなくなりました。")
        return redirect(reverse("admin:chiebukuro_boardsettings_changelist"))

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

    list_display = ["short_body", "theme", "region", "status", "release_rank", "release_open", "source", "nickname", "answer_count", "interest_count", "home_pick", "created_at"]
    list_display_links = ["short_body"]
    list_editable = ["theme", "region", "status", "release_rank", "home_pick"]
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


class UnhelpfulFilter(admin.SimpleListFilter):
    """「わかりません」「ありません」など、質問した人の役に立たなさそうな短い回答をまとめて確認する"""

    title = "役に立たないかも"
    parameter_name = "unhelpful"
    WORDS = ["わかりません", "分かりません", "わからない", "分からない", "ありません", "特にない", "とくにない", "特になし", "知らない", "知りません", "なし", "ない"]

    def lookups(self, request, model_admin):
        return [("yes", "短い回答・「わかりません」など")]

    def queryset(self, request, queryset):
        if self.value() != "yes":
            return queryset
        from django.db.models.functions import Length

        words = Q()
        for word in self.WORDS:
            words |= Q(body__icontains=word)
        return queryset.annotate(body_length=Length("body")).filter(Q(body_length__lte=12) | (words & Q(body_length__lte=40)))


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):

    list_display = ["short_body", "question", "nickname", "status", "from_survey", "is_staff", "home_pick", "created_at"]
    list_editable = ["status", "is_staff", "home_pick"]
    list_filter = [UnhelpfulFilter, "status", "from_survey", "is_staff"]
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

    list_display = ["title", "kind", "genre", "state", "status", "region", "nickname", "request_count", "created_at"]
    list_editable = ["status"]
    list_filter = ["kind", "genre", "state", "status", "region"]
    search_fields = ["title", "body", "nickname", "owner__username"]
    readonly_fields = ["owner"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(requests_total=Count("requests"))

    @admin.display(description="やりとり", ordering="requests_total")
    def request_count(self, obj):
        return obj.requests_total


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):

    list_display = ["title", "kind", "status", "is_sample", "region", "nickname", "expires_at", "created_at"]
    list_editable = ["status"]
    list_filter = ["is_sample", "kind", "status", "region"]
    search_fields = ["title", "body", "nickname", "owner__username"]
    readonly_fields = ["owner"]
    actions = ["delete_samples"]

    @admin.action(description="テスト用（架空）の告知をすべて消す（選んだものに関係なく）")
    def delete_samples(self, request, queryset):
        count, _ = Notice.objects.filter(is_sample=True).delete()
        self.message_user(request, f"テスト用の告知と、その問い合わせを消しました（{count}件）。")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ["sender", "body", "created_at"]
    readonly_fields = fields
    can_delete = False


@admin.register(ItemRequest)
class ItemRequestAdmin(admin.ModelAdmin):
    """トラブルの確認用 (読むだけ)"""

    list_display = ["__str__", "nickname", "is_chosen", "last_message_at"]
    list_filter = ["is_chosen"]
    search_fields = ["item__title", "notice__title", "nickname", "requester__username"]
    inlines = [MessageInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PostReplyInline(admin.TabularInline):
    model = PostReply
    extra = 0
    fields = ["body", "nickname", "status", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):

    list_display = ["short_body", "theme", "region", "nickname", "status", "home_pick", "created_at"]
    list_editable = ["status", "home_pick"]
    list_filter = ["status", "bot", "theme", "region"]
    search_fields = ["body", "nickname", "author__username"]
    readonly_fields = ["author"]
    inlines = [PostReplyInline]

    @admin.display(description="つぶやき")
    def short_body(self, obj):
        return obj.body if len(obj.body) <= 50 else obj.body[:50] + "…"


@admin.register(BotPost)
class BotPostAdmin(admin.ModelAdmin):
    """Botの予約つぶやき。時間になると、掲示板が開かれたときに出ます。"""

    list_display = ["publish_at", "bot", "day", "theme", "short_title", "is_active", "state", "post_link", "note"]
    list_editable = ["is_active"]
    list_filter = ["state", "bot", "is_active"]
    search_fields = ["title", "body"]
    date_hierarchy = "publish_at"
    readonly_fields = ["state", "ref", "note", "post_link"]
    fields = ["bot", "publish_at", "day", "theme", "title", "body", "source_url", "is_active", "state", "post_link", "ref", "note"]
    actions = ["post_now", "back_to_waiting"]

    @admin.display(description="見出し")
    def short_title(self, obj):
        text = obj.title or obj.body or "（投稿の時間に自動で作ります）"
        return text if len(text) <= 40 else text[:40] + "…"

    @admin.display(description="つぶやき")
    def post_link(self, obj):
        if not obj.post_id:
            return "-"
        return format_html('<a href="{}">見る</a>', reverse("chiebukuro:post", args=[obj.post_id]))

    @admin.action(description="選んだ予約を今すぐ投稿する")
    def post_now(self, request, queryset):
        from django.utils import timezone

        from .bots import release_due

        now = timezone.now()
        queryset.filter(state=BotPost.State.WAITING).update(publish_at=now)
        count = release_due(now=now + timedelta(seconds=1), limit=50)
        self.message_user(request, f"{count}件を投稿しました。（データがないものは「見送り」になります）")

    @admin.action(description="選んだ予約を「予約中」にもどす（つぶやきは消えません）")
    def back_to_waiting(self, request, queryset):
        count = queryset.exclude(state=BotPost.State.WAITING).update(state=BotPost.State.WAITING, post=None, note="")
        self.message_user(request, f"{count}件を予約中にもどしました。")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):

    list_display = ["created_at", "kind", "message", "email", "user", "handled"]
    list_editable = ["handled"]
    list_filter = ["handled", "kind"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):

    list_display = ["created_at", "target", "target_link", "reason", "reporter", "handled"]
    list_editable = ["handled"]
    list_filter = ["handled", "target"]

    @admin.display(description="対象")
    def target_link(self, obj):
        from django.utils.html import format_html

        names = {"question": "question", "answer": "answer", "item": "item", "post": "post", "notice": "notice"}
        if obj.target not in names:
            return obj.target_id
        url = reverse(f"admin:chiebukuro_{names[obj.target]}_change", args=[obj.target_id])
        return format_html('<a href="{}">#{} を開く</a>', url, obj.target_id)


class PollChoiceInline(admin.TabularInline):
    model = PollChoice
    extra = 4
    fields = ["label", "order", "vote_count"]
    readonly_fields = ["vote_count"]

    @admin.display(description="票")
    def vote_count(self, obj):
        return obj.votes.count() if obj.pk else ""


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    """HOME の「みんなのアンケート」。まだ答えていない新しいものから HOME に出ます"""

    list_display = ["question", "is_active", "vote_total", "created_at"]
    list_editable = ["is_active"]
    inlines = [PollChoiceInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(votes_total=Count("votes"))

    @admin.display(description="回答数", ordering="votes_total")
    def vote_total(self, obj):
        return obj.votes_total


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    """HOME の広告枠。期間中のものが、日ごとに順番に出ます"""

    list_display = ["name", "title", "starts_on", "ends_on", "is_active", "clicks"]
    list_editable = ["is_active"]
    readonly_fields = ["clicks"]
