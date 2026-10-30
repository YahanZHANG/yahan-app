from django.db.utils import (
    OperationalError,
    ProgrammingError,
)
from django.db.models import Q
from django.urls import reverse

from news.models import (
    NewsFeedback,
    SupportRequest,
)

from portal.models import (
    AppAccessRequest,
)

from outings.models import (
    Event,
)

from washoku.models import (
    Comment as WashokuComment,
    Feedback as WashokuFeedback,
    MemberPhoto as WashokuMemberPhoto,
    PollSuggestion as WashokuPollSuggestion,
    Post as WashokuPost,
    Recipe as WashokuRecipe,
    Substitute as WashokuSubstitute,
)


# =========================================================
# Admin Attention Counts
# =========================================================

def _item(label, count, url_name, query=""):
    return {
        "label": label,
        "count": count,
        "url": reverse(url_name) + (f"?{query}" if query else ""),
    }


def _washoku_items():

    unchecked = WashokuComment.objects.filter(
        admin_checked=False,
        is_deleted=False,
    )
    # 質問とお店の口コミは、それぞれの一覧で確認する
    questions = unchecked.filter(parent__isnull=True, kind="question")
    store_reviews = unchecked.filter(parent__isnull=True, store__isnull=False).exclude(kind="question")
    other_comments = unchecked.exclude(pk__in=questions.values("pk")).exclude(pk__in=store_reviews.values("pk"))

    comments_url = "admin:washoku_comment_changelist"

    # 投稿: 公開中でまだ確認していないものと、確認待ち (予約なし)
    posts_to_check = WashokuPost.objects.filter(
        Q(status="published", admin_checked=False) | Q(status="draft", publish_at__isnull=True)
    )

    def post_item(label, kind, model):
        return _item(
            label,
            posts_to_check.filter(kind=kind).count(),
            f"admin:washoku_{model}_changelist",
            "state=unchecked" if not posts_to_check.filter(kind=kind, status="draft").exists() else "state=pending",
        )

    return [
        _item(
            "投稿レシピ",
            WashokuRecipe.objects.filter(origin="member", status="draft").count(),
            "admin:washoku_recipe_changelist",
            "origin__exact=member&status__exact=draft",
        ),
        post_item("コラム", "column", "columnpost"),
        post_item("口コミ（買ったもの）", "product", "reviewpost"),
        post_item("参考リンク", "link", "linkpost"),
        _item(
            "Q&A",
            questions.count(),
            "admin:washoku_questioncomment_changelist",
            "state=unchecked",
        ),
        _item(
            "お店の口コミ",
            store_reviews.count(),
            "admin:washoku_storereview_changelist",
            "state=unchecked",
        ),
        _item(
            "レシピへのコメント",
            other_comments.filter(recipe__isnull=False).count(),
            comments_url,
            "state=unchecked&target=recipe",
        ),
        _item(
            "食材へのコメント",
            other_comments.filter(ingredient__isnull=False).count(),
            comments_url,
            "state=unchecked&target=ingredient",
        ),
        _item(
            "コラム・口コミへのコメント",
            other_comments.filter(post__isnull=False).count(),
            comments_url,
            "state=unchecked&target=post",
        ),
        _item(
            "投稿された写真",
            WashokuMemberPhoto.objects.filter(admin_checked=False).count(),
            "admin:washoku_memberphoto_changelist",
            "admin_checked__exact=0",
        ),
        _item(
            "代用品の投稿",
            WashokuSubstitute.objects.filter(status="draft").count(),
            "admin:washoku_substitute_changelist",
            "status__exact=draft",
        ),
        _item(
            "アンケートの提案",
            WashokuPollSuggestion.objects.filter(status="new").count(),
            "admin:washoku_pollsuggestion_changelist",
            "status__exact=new",
        ),
        _item(
            "質問箱",
            WashokuFeedback.objects.filter(is_read=False).count(),
            "admin:washoku_feedback_changelist",
            "is_read__exact=0",
        ),
    ]


def admin_attention_counts(request):

    # Admin以外は集計しない
    if (
        not request.user.is_authenticated
        or not request.user.is_staff
    ):
        return {}

    try:

        groups = [
            {
                "app": "Swiss News",
                "items": [
                    _item(
                        "ご意見・ご要望",
                        NewsFeedback.objects.filter(is_read=False).count(),
                        "admin:news_newsfeedback_changelist",
                        "is_read__exact=0",
                    ),
                    _item(
                        "応援の問い合わせ",
                        SupportRequest.objects.filter(is_read=False).count(),
                        "admin:news_supportrequest_changelist",
                        "is_read__exact=0",
                    ),
                ],
            },
            {
                "app": "おでかけ",
                "items": [
                    _item(
                        "イベント承認",
                        Event.objects.filter(status=Event.Status.PENDING).count(),
                        "admin:outings_event_changelist",
                        "status__exact=pending",
                    ),
                ],
            },
            {
                "app": "スイスで和食",
                "items": _washoku_items(),
            },
            {
                "app": "Yapp",
                "items": [
                    _item(
                        "アプリの利用申請",
                        AppAccessRequest.objects.filter(
                            status=AppAccessRequest.Status.PENDING
                        ).count(),
                        "admin:portal_appaccessrequest_changelist",
                        "status__exact=pending",
                    ),
                ],
            },
        ]

    except (
        OperationalError,
        ProgrammingError,
    ):
        # マイグレーション前など、
        # テーブルが存在しない場合に備える
        return {}

    # 件数のある項目だけを出す
    for group in groups:
        group["items"] = [item for item in group["items"] if item["count"]]
        group["total"] = sum(item["count"] for item in group["items"])

    groups = [group for group in groups if group["items"]]

    return {
        "admin_attention": {
            "groups": groups,
            "total": sum(group["total"] for group in groups),
        }
    }
