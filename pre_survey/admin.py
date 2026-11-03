"""
事前アンケートの管理画面 (スタッフのみ)

質問: 公開・非公開・却下の切り替え、テーマの変更、回答数・「知りたい」数で並べ替え、CSV
回答: 一覧、非表示の切り替え、CSV
"""

import csv

from django.contrib import admin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone

from .features import FEATURE_CHOICES
from .models import Answer, FeatureWish, Participant, Question


def csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}-{timezone.localdate():%Y%m%d}.csv"'
    # Excel で文字化けしないように BOM を付ける
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


def local(value):
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M") if value else ""


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    fields = ["body", "nickname", "is_hidden", "created_at"]
    readonly_fields = ["created_at"]
    show_change_link = True


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):

    list_display = [
        "short_body",
        "theme",
        "status",
        "source",
        "region",
        "author",
        "answer_count",
        "interest_count",
        "skip_count",
        "created_at",
    ]
    list_display_links = ["short_body"]
    list_editable = ["theme", "status"]
    list_filter = ["status", "theme", "source", "region"]
    search_fields = ["body", "nickname"]
    ordering = ["-created_at"]
    list_per_page = 100
    inlines = [AnswerInline]
    readonly_fields = ["source", "user", "participant", "browser_token", "seed_key", "created_at", "updated_at"]
    fields = [
        "body",
        "theme",
        "region",
        "status",
        "nickname",
        "source",
        "user",
        "participant",
        "browser_token",
        "seed_key",
        "created_at",
        "updated_at",
    ]
    actions = ["publish", "hide", "reject", "export_csv"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user").annotate(
            answers_total=Count("answers", filter=Q(answers__is_hidden=False), distinct=True),
            interests_total=Count("interests", distinct=True),
            skips_total=Count("skips", distinct=True),
        )

    @admin.display(description="質問")
    def short_body(self, obj):
        return obj.body if len(obj.body) <= 60 else obj.body[:60] + "…"

    @admin.display(description="投稿者")
    def author(self, obj):
        if obj.source == Question.Source.STAFF:
            return "運営"
        name = obj.display_name
        return f"{name} ({obj.user.username})" if obj.user else name

    @admin.display(description="回答", ordering="answers_total")
    def answer_count(self, obj):
        return obj.answers_total

    @admin.display(description="知りたい", ordering="interests_total")
    def interest_count(self, obj):
        return obj.interests_total

    @admin.display(description="スキップ", ordering="skips_total")
    def skip_count(self, obj):
        return obj.skips_total

    def _set_status(self, request, queryset, status, label):
        count = queryset.update(status=status)
        self.message_user(request, f"{count}件を「{label}」にしました。")

    @admin.action(description="公開する")
    def publish(self, request, queryset):
        self._set_status(request, queryset, Question.Status.PUBLISHED, "公開")

    @admin.action(description="非公開にする")
    def hide(self, request, queryset):
        self._set_status(request, queryset, Question.Status.HIDDEN, "非公開")

    @admin.action(description="却下する")
    def reject(self, request, queryset):
        self._set_status(request, queryset, Question.Status.REJECTED, "却下")

    @admin.action(description="選んだ質問をCSVで書き出す")
    def export_csv(self, request, queryset):
        rows = (
            [
                q.pk,
                q.get_theme_display(),
                q.get_region_display() if q.region else "",
                q.get_source_display(),
                q.get_status_display(),
                q.display_name,
                q.user.username if q.user else "",
                q.body,
                q.answers_total,
                q.interests_total,
                q.skips_total,
                local(q.created_at),
            ]
            for q in queryset.order_by("pk")
        )
        return csv_response(
            "pre-survey-questions",
            ["ID", "テーマ", "地域", "作成者", "ステータス", "ニックネーム", "ユーザーID",
             "質問", "回答数", "知りたい", "スキップ", "作成日時"],
            rows,
        )


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):

    list_display = ["short_body", "question_link", "nickname_label", "is_hidden", "publish_consent", "created_at"]
    list_display_links = ["short_body"]
    list_editable = ["is_hidden"]
    list_filter = ["is_hidden", "question__theme", "question__source"]
    search_fields = ["body", "nickname", "question__body"]
    ordering = ["-created_at"]
    list_per_page = 100
    readonly_fields = ["question", "user", "participant", "browser_token", "publish_consent", "created_at"]
    fields = ["question", "body", "nickname", "is_hidden", "publish_consent", "user", "participant", "browser_token", "created_at"]
    actions = ["hide", "show", "export_csv"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("question", "user")

    @admin.display(description="回答")
    def short_body(self, obj):
        return obj.body if len(obj.body) <= 60 else obj.body[:60] + "…"

    @admin.display(description="質問", ordering="question__body")
    def question_link(self, obj):
        return str(obj.question)

    @admin.display(description="ニックネーム", ordering="nickname")
    def nickname_label(self, obj):
        return obj.display_name

    @admin.action(description="非表示にする")
    def hide(self, request, queryset):
        count = queryset.update(is_hidden=True)
        self.message_user(request, f"{count}件を非表示にしました。")

    @admin.action(description="表示する")
    def show(self, request, queryset):
        count = queryset.update(is_hidden=False)
        self.message_user(request, f"{count}件を表示にしました。")

    @admin.action(description="選んだ回答をCSVで書き出す")
    def export_csv(self, request, queryset):
        rows = (
            [
                a.pk,
                a.question_id,
                a.question.get_theme_display(),
                a.question.body,
                a.display_name,
                a.user.username if a.user else "",
                a.body,
                "非表示" if a.is_hidden else "",
                "同意" if a.publish_consent else "",
                local(a.created_at),
            ]
            for a in queryset.order_by("question_id", "pk")
        )
        return csv_response(
            "pre-survey-answers",
            ["ID", "質問ID", "テーマ", "質問", "ニックネーム", "ユーザーID", "回答", "非表示", "公開同意", "回答日時"],
            rows,
        )


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):

    list_display = ["display_name", "nickname_mode", "theme_list", "region", "user", "answer_count",
                    "question_count", "consent_version", "created_at", "finished_at"]
    list_filter = ["nickname_mode", "region", "consent_version"]
    search_fields = ["nickname", "user__username"]
    ordering = ["-created_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user").annotate(
            answers_total=Count("answers", distinct=True),
            questions_total=Count("questions", distinct=True),
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="ニックネーム")
    def display_name(self, obj):
        return obj.display_name

    @admin.display(description="テーマ")
    def theme_list(self, obj):
        return "・".join(obj.theme_labels())

    @admin.display(description="回答", ordering="answers_total")
    def answer_count(self, obj):
        return obj.answers_total

    @admin.display(description="質問", ordering="questions_total")
    def question_count(self, obj):
        return obj.questions_total


@admin.register(FeatureWish)
class FeatureWishAdmin(admin.ModelAdmin):
    """「0問目」: 掲示板に求める機能。一覧の上に、選択肢ごとの票数を出す。"""

    change_list_template = "admin/pre_survey/featurewish/change_list.html"
    list_display = ["created_at", "response", "feature_list", "other_text", "short_comment", "who"]
    list_filter = ["response"]
    search_fields = ["other_text", "comment"]
    ordering = ["-created_at"]
    list_per_page = 100
    actions = ["export_csv"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("participant", "user")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="選んだ機能")
    def feature_list(self, obj):
        return "・".join(obj.feature_labels())

    @admin.display(description="ご意見")
    def short_comment(self, obj):
        return obj.comment if len(obj.comment) <= 60 else obj.comment[:60] + "…"

    @admin.display(description="ニックネーム")
    def who(self, obj):
        if obj.participant:
            return obj.participant.display_name
        return obj.user.username if obj.user else ""

    def changelist_view(self, request, extra_context=None):
        answered = FeatureWish.objects.filter(response=FeatureWish.Response.ANSWERED)
        counts = {key: 0 for key, _ in FEATURE_CHOICES}
        for features in answered.values_list("features", flat=True):
            for key in features:
                counts[key] = counts.get(key, 0) + 1
        total = answered.count()
        tally = [
            {"label": label, "count": counts.get(key, 0), "percent": round(counts.get(key, 0) * 100 / total) if total else 0}
            for key, label in FEATURE_CHOICES
        ]
        tally.sort(key=lambda row: -row["count"])
        extra_context = {
            **(extra_context or {}),
            "wish_tally": tally,
            "wish_total": total,
            "wish_skipped": FeatureWish.objects.filter(response=FeatureWish.Response.SKIPPED).count(),
            "wish_already": FeatureWish.objects.filter(response=FeatureWish.Response.ALREADY).count(),
        }
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description="選んだものをCSVで書き出す")
    def export_csv(self, request, queryset):
        keys = [key for key, _ in FEATURE_CHOICES]
        rows = (
            [
                w.pk,
                local(w.created_at),
                w.get_response_display(),
                w.participant.display_name if w.participant else "",
                w.user.username if w.user else "",
                *["1" if key in w.features else "" for key in keys],
                w.other_text,
                w.comment,
            ]
            for w in queryset.order_by("pk")
        )
        return csv_response(
            "pre-survey-feature-wishes",
            ["ID", "日時", "状態", "ニックネーム", "ユーザーID", *[label for _, label in FEATURE_CHOICES], "その他の内容", "ご意見"],
            rows,
        )
