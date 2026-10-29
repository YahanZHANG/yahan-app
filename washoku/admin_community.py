"""
管理画面: コミュニティの投稿を種類ごとに分けて扱う。

コラム・アンケート・口コミ・参考リンク・Q&A・お店の口コミを、それぞれ別のメニューにする
(中身は Post / Comment の同じテーブル。models.py の代理モデル)。
一覧の上に「状態」のタブ (件数つき) を出し、予約・確認待ち・公開中の未確認/確認済み・保留・却下を切り替える。
"""

from datetime import timedelta

from django.contrib import admin
from django.db.models import BooleanField, Case, Count, Exists, OuterRef, Q, Value, When
from django.utils import timezone
from django.utils.html import format_html

from .admin import (
    CommentAdmin,
    CommentTargetFilter,
    PollAnswerInline,
    PollChoiceInline,
    PollVoteInline,
    PostAdmin,
)
from .models import (
    ColumnPost,
    Comment,
    LinkPost,
    PollPost,
    Post,
    QuestionComment,
    ReviewPost,
    StoreReview,
)


# 答えのない質問を「古い」とする日数 (HOME に出さなくなる日数と同じ)
OLD_QUESTION_DAYS = 21


# =========================================================
# 状態のタブ
# =========================================================

def post_states():
    """投稿の状態: (キー, タブの名前, 絞り込み)"""

    return [
        ("scheduled", "⏰ 予約投稿", Q(status="draft", publish_at__isnull=False)),
        ("pending", "📝 確認待ち（非公開）", Q(status="draft", publish_at__isnull=True)),
        ("unchecked", "🆕 公開中・未確認", Q(status="published", admin_checked=False)),
        ("checked", "✅ 公開中・確認済み", Q(status="published", admin_checked=True)),
        ("hold", "⏸ 保留", Q(status="hold")),
        ("rejected", "🚫 却下", Q(status="rejected")),
    ]


def comment_states():
    """コメントの状態"""

    return [
        ("unchecked", "🆕 未確認", Q(admin_checked=False, is_deleted=False, is_hidden=False)),
        ("checked", "✅ 確認済み", Q(admin_checked=True, is_deleted=False, is_hidden=False)),
        ("hidden", "🙈 非表示", Q(is_hidden=True)),
        ("deleted", "🗑 投稿者が削除", Q(is_deleted=True)),
    ]


def question_states():
    """質問の状態 (答えがあるか、古いか)"""

    old = timezone.now() - timedelta(days=OLD_QUESTION_DAYS)
    visible = Q(is_deleted=False, is_hidden=False)

    return [
        ("open", "🙋 答え待ち", visible & Q(has_answer=False, created_at__gte=old)),
        ("old", "💤 3週間以上答えなし", visible & Q(has_answer=False, created_at__lt=old)),
        ("solved", "✅ 解決済み", visible & Q(has_answer=True)),
        ("unchecked", "🆕 未確認", visible & Q(admin_checked=False)),
        ("hidden", "🙈 非表示・削除", Q(is_hidden=True) | Q(is_deleted=True)),
    ]


class StateFilter(admin.SimpleListFilter):
    """右側の絞り込みにも、上のタブと同じ「状態」を出す"""

    title = "状態"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return [(key, label) for key, label, _ in model_admin.states()]

    def queryset(self, request, queryset):
        for key, _, condition in self.model_admin_states:
            if self.value() == key:
                return queryset.filter(condition)
        return queryset

    def __init__(self, request, params, model, model_admin):
        self.model_admin_states = model_admin.states()
        super().__init__(request, params, model, model_admin)


class StateTabsMixin:
    """一覧の上に、状態ごとのタブ (件数つき) を出す"""

    change_list_template = "admin/washoku/state_tabs_change_list.html"

    def states(self):
        return post_states()

    def changelist_view(self, request, extra_context=None):

        base = self.get_queryset(request)
        current = request.GET.get("state", "")
        tabs = [{"label": "すべて", "count": base.count(), "url": "?", "active": not current, "key": ""}]

        for key, label, condition in self.states():
            tabs.append({
                "label": label,
                "count": base.filter(condition).count(),
                "url": f"?state={key}",
                "active": current == key,
                "key": key,
            })

        extra_context = {**(extra_context or {}), "state_tabs": tabs, "section_note": self.section_note}
        return super().changelist_view(request, extra_context)

    section_note = ""


def post_state(post):
    """投稿の状態のキーと表示"""

    if post.status == "draft":
        if post.publish_at:
            at = timezone.localtime(post.publish_at)
            return "scheduled", f"⏰ {at.month}/{at.day} {at:%H:%M} 公開予定"
        return "pending", "📝 確認待ち"

    if post.status == "published":
        return ("checked", "✅ 確認済み") if post.admin_checked else ("unchecked", "🆕 未確認")

    return post.status, dict(post_states_labels()).get(post.status, post.get_status_display())


def post_states_labels():
    return [(key, label) for key, label, _ in post_states()]


def state_badge(key, label):
    return format_html('<span class="yapp-state yapp-state-{}">{}</span>', key, label)


# =========================================================
# 投稿 (コラム・アンケート・口コミ・参考リンク)
# =========================================================

PUBLISH_FIELDSET = (
    "公開と確認",
    {
        "fields": ("status", "publish_at", "admin_checked", "admin_note", "author", "created_at", "updated_at"),
        "description": "予約投稿: 「確認待ち・予約」のまま「公開予約」に日時を入れると、その時刻に公開されます。"
        "保留・却下は会員には「非公開」と表示されます（理由は管理メモへ）。",
    },
)

HOME_FIELDSET = (
    "HOMEの注目",
    {
        "fields": ("is_featured", "featured_order", "featured_hidden", "home_photo_url", "home_photo_upload", "home_photo_preview"),
        "classes": ("collapse",),
    },
)


class PostSectionAdmin(StateTabsMixin, PostAdmin):
    """種類ごとの投稿の管理 (コラム・アンケート・口コミ・参考リンクで共通)"""

    section_kind = None
    inlines = ()
    list_editable = ()

    list_display_links = ("title",)
    list_per_page = 50
    date_hierarchy = "created_at"

    search_fields = (
        "title",
        "body",
        "author__username",
        "admin_note",
    )

    actions = [
        "mark_checked",
        "publish",
        "hold",
        "reject",
        "unpublish",
        "feature",
        "unfeature",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(kind=self.section_kind).select_related("author")

    def save_model(self, request, obj, form, change):

        obj.kind = self.section_kind

        # 管理者が開いて保存したものは確認済み (チェックを外して保存したときはそのまま)
        if "admin_checked" not in form.changed_data:
            obj.admin_checked = True

        super().save_model(request, obj, form, change)

    @admin.display(description="状態", ordering="status")
    def state(self, obj):
        return state_badge(*post_state(obj))

    @admin.display(description="書いた人", ordering="author__username")
    def author_name(self, obj):
        return obj.author.username if obj.author_id else "—"

    @admin.display(description="日時", ordering="created_at")
    def when(self, obj):
        return timezone.localtime(obj.created_at).strftime("%Y/%m/%d %H:%M")

    @admin.action(description="✅ 確認済みにする")
    def mark_checked(self, request, queryset):
        updated = queryset.update(admin_checked=True)
        self.message_user(request, f"{updated}件を確認済みにしました。")

    @admin.action(description="公開する（確認済みにする）")
    def publish(self, request, queryset):
        # 確認待ちから公開したものは、一覧の一番上に来るよう投稿日時を今にする
        fresh = queryset.filter(status="draft").update(status="published", admin_checked=True, created_at=timezone.now())
        back = queryset.filter(status__in=("hold", "rejected")).update(status="published", admin_checked=True)
        self.message_user(request, f"{fresh + back}件を公開しました。")

    @admin.action(description="⏸ 保留にする（非公開）")
    def hold(self, request, queryset):
        updated = queryset.update(status="hold", is_featured=False, admin_checked=True)
        self.message_user(request, f"{updated}件を保留にしました。理由は「管理メモ」に残せます。")

    @admin.action(description="🚫 却下する（非公開）")
    def reject(self, request, queryset):
        updated = queryset.update(status="rejected", is_featured=False, show_result=False, admin_checked=True)
        self.message_user(request, f"{updated}件を却下しました。")

    @admin.action(description="📝 確認待ちに戻す（非公開）")
    def unpublish(self, request, queryset):
        updated = queryset.update(status="draft")
        self.message_user(request, f"{updated}件を確認待ちに戻しました。")


@admin.register(ColumnPost)
class ColumnPostAdmin(PostSectionAdmin):
    section_kind = "column"
    section_note = "コラムの最後にアンケートを付けるときは、下の「選択肢」を入れます。"
    inlines = (PollChoiceInline, PollVoteInline, PollAnswerInline)

    list_display = ("title", "state", "author_name", "when", "comment_total", "is_featured", "featured_order", "on_home")
    list_editable = ("is_featured", "featured_order")
    list_filter = (StateFilter, "is_featured", "featured_hidden")

    fieldsets = (
        (None, {"fields": ("title", "body", "photo_1", "photo_2", "ingredients")}),
        PUBLISH_FIELDSET,
        HOME_FIELDSET,
        ("コラムの最後のアンケート", {"fields": ("poll_question", "poll_type", "show_result"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            comments_total=Count("comments", filter=Q(comments__is_deleted=False), distinct=True)
        )

    @admin.display(description="コメント", ordering="comments_total")
    def comment_total(self, obj):
        return obj.comments_total or ""


@admin.register(PollPost)
class PollPostAdmin(PostSectionAdmin):
    section_kind = "poll"
    section_note = "「結果をHOMEに出す」にチェックしたもの（新しい順に2つまで）が、HOMEの「人気アンケートの結果」に出ます。"
    inlines = (PollChoiceInline, PollVoteInline, PollAnswerInline)

    list_display = ("title", "poll_type", "state", "respondents", "show_result", "when")
    list_editable = ("show_result",)
    list_filter = (StateFilter, "poll_type", "show_result")

    fieldsets = (
        (None, {"fields": ("title", "poll_type", "body")}),
        PUBLISH_FIELDSET,
        ("HOMEに出す", {"fields": ("show_result",)}),
        HOME_FIELDSET,
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            voter_total=Count("votes__voter_key", distinct=True),
            user_total=Count("votes__user", distinct=True),
            answer_total=Count("answers", distinct=True),
        )

    @admin.display(description="回答")
    def respondents(self, obj):
        if obj.poll_type == "text":
            return f"{obj.answer_total}件"
        return f"{max(obj.voter_total, obj.user_total)}人"


@admin.register(ReviewPost)
class ReviewPostAdmin(PostSectionAdmin):
    section_kind = "product"
    section_note = "スーパーなどで買ったものの口コミです。お店そのものの口コミは「お店の口コミ」へ。"

    list_display = ("title", "verdict", "shop_names", "state", "author_name", "when")
    list_filter = (StateFilter, "verdict", "section")

    fieldsets = (
        (None, {"fields": ("title", "verdict", "shop", "section", "resembles", "body", "photo_1", "photo_2", "ingredients")}),
        PUBLISH_FIELDSET,
        HOME_FIELDSET,
    )


@admin.register(LinkPost)
class LinkPostAdmin(PostSectionAdmin):
    section_kind = "link"
    section_note = "記事を写さず、要点を自分の言葉で短く書き、出典とリンクを載せます。"

    list_display = ("title", "source", "state", "when")
    list_filter = (StateFilter,)

    fieldsets = (
        (None, {"fields": ("title", "url", "source", "body", "ingredients")}),
        PUBLISH_FIELDSET,
        HOME_FIELDSET,
    )


# =========================================================
# コメント (Q&A・お店の口コミ)
# =========================================================

class CommentSectionAdmin(StateTabsMixin, CommentAdmin):

    list_editable = ()

    list_display_links = ("short_body",)
    list_per_page = 50
    date_hierarchy = "created_at"
    readonly_fields = ("home_photo_preview", "edited_at", "created_at")

    actions = [
        "mark_checked",
        "hide",
        "show",
    ]

    def states(self):
        return comment_states()

    def save_model(self, request, obj, form, change):
        if "admin_checked" not in form.changed_data:
            obj.admin_checked = True
        super().save_model(request, obj, form, change)

    @admin.display(description="状態")
    def state(self, obj):
        for key, label, _ in comment_states():
            if key == "deleted" and obj.is_deleted:
                return state_badge(key, label)
            if key == "hidden" and obj.is_hidden:
                return state_badge(key, label)
        return state_badge(*(("checked", "✅ 確認済み") if obj.admin_checked else ("unchecked", "🆕 未確認")))

    @admin.display(description="書いた人", ordering="author__username")
    def author_name(self, obj):
        return obj.author.username

    @admin.display(description="日時", ordering="created_at")
    def when(self, obj):
        return timezone.localtime(obj.created_at).strftime("%Y/%m/%d %H:%M")

    @admin.display(description="返信", ordering="reply_total")
    def replies(self, obj):
        return obj.reply_total or ""


@admin.register(QuestionComment)
class QuestionCommentAdmin(CommentSectionAdmin):
    section_note = "3週間たっても答えのない質問は、HOMEに出ません（「HOMEに残す期限」を入れたものは出ます）。"

    list_display = ("short_body", "answer_state", "target_label", "author_name", "replies", "reopened", "home_hidden", "home_until_text", "when")
    list_editable = ("reopened", "home_hidden")
    list_filter = (StateFilter, CommentTargetFilter, "home_hidden", "reopened")

    fieldsets = (
        (None, {"fields": ("body", "author", "photo_url", "recipe", "ingredient", "store", "post")}),
        ("管理", {"fields": ("admin_checked", "is_hidden", "reopened", "home_hidden", "home_until", "edited_at", "created_at")}),
        HOME_FIELDSET,
    )

    def states(self):
        return question_states()

    def get_queryset(self, request):

        answers = Comment.objects.filter(parent=OuterRef("pk"), is_hidden=False, is_deleted=False)

        return (
            super().get_queryset(request)
            .filter(parent__isnull=True, kind="question")
            .select_related("author", "recipe", "ingredient", "store", "post")
            .annotate(
                has_answer=Case(
                    When(reopened=True, then=Value(False)),
                    When(Exists(answers.filter(reopened=True)), then=Value(False)),
                    default=Exists(answers),
                    output_field=BooleanField(),
                ),
                reply_total=Count("replies", filter=Q(replies__is_deleted=False, replies__is_hidden=False), distinct=True),
            )
        )

    @admin.display(description="HOMEに残す期限", ordering="home_until")
    def home_until_text(self, obj):
        if not obj.home_until:
            return "—"
        at = timezone.localtime(obj.home_until)
        return f"{at.month}/{at.day} {at:%H:%M}まで"

    @admin.display(description="答え")
    def answer_state(self, obj):
        if obj.is_hidden or obj.is_deleted:
            return state_badge("hidden", "🙈 非表示")
        if obj.has_answer:
            return state_badge("checked", "✅ 解決済み")
        if obj.created_at < timezone.now() - timedelta(days=OLD_QUESTION_DAYS):
            return state_badge("old", "💤 3週間以上")
        return state_badge("open", "🙋 答え待ち")


@admin.register(StoreReview)
class StoreReviewAdmin(CommentSectionAdmin):
    section_note = "お店のページに書かれた口コミです（コミュニティの「口コミ」にも並びます）。"

    list_display = ("short_body", "store_name", "verdict", "state", "author_name", "replies", "when", "admin_checked")
    list_editable = ("admin_checked",)
    list_filter = (StateFilter, "verdict", ("store", admin.RelatedOnlyFieldListFilter))

    fieldsets = (
        (None, {"fields": ("store", "verdict", "body", "photo_url", "author")}),
        ("管理", {"fields": ("admin_checked", "is_hidden", "edited_at", "created_at")}),
        HOME_FIELDSET,
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .filter(store__isnull=False, parent__isnull=True)
            .exclude(kind="question")
            .select_related("author", "store")
            .annotate(reply_total=Count("replies", filter=Q(replies__is_deleted=False), distinct=True))
        )

    @admin.display(description="お店", ordering="store__name")
    def store_name(self, obj):
        return obj.store.name


# =========================================================
# まとめて見る (すべての投稿・すべてのコメント) にも状態のタブを付ける
# =========================================================

admin.site.unregister(Post)
admin.site.unregister(Comment)


@admin.register(Post)
class AllPostAdmin(StateTabsMixin, PostAdmin):
    section_note = "ふだんは左の「コラム」「アンケート」などから。ここはすべての種類をまとめて見るところです。"

    list_display = ("title", "kind", "state", "is_featured", "featured_order", "featured_hidden", "on_home", "show_result", "author", "created_at")
    list_filter = (StateFilter, "kind", "is_featured", "featured_hidden", "show_result", "section")
    actions = PostSectionAdmin.actions

    mark_checked = PostSectionAdmin.mark_checked
    publish = PostSectionAdmin.publish
    hold = PostSectionAdmin.hold
    reject = PostSectionAdmin.reject
    unpublish = PostSectionAdmin.unpublish
    state = PostSectionAdmin.state


@admin.register(Comment)
class AllCommentAdmin(StateTabsMixin, CommentAdmin):
    section_note = "レシピ・食材・コラムへのコメントもここに。質問は「Q&A」、お店の口コミは「お店の口コミ」が見やすいです。"

    def states(self):
        return comment_states()
