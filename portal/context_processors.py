from django.db.utils import (
    OperationalError,
    ProgrammingError,
)
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
    Recipe as WashokuRecipe,
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

    comments_url = "admin:washoku_comment_changelist"

    return [
        _item(
            "投稿レシピ",
            WashokuRecipe.objects.filter(origin="member", status="draft").count(),
            "admin:washoku_recipe_changelist",
            "origin__exact=member&status__exact=draft",
        ),
        _item(
            "レシピへのコメント",
            unchecked.filter(recipe__isnull=False).count(),
            comments_url,
            "admin_checked__exact=0&target=recipe",
        ),
        _item(
            "食材へのコメント",
            unchecked.filter(ingredient__isnull=False).count(),
            comments_url,
            "admin_checked__exact=0&target=ingredient",
        ),
        _item(
            "お店の口コミ",
            unchecked.filter(store__isnull=False).count(),
            comments_url,
            "admin_checked__exact=0&target=store",
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
