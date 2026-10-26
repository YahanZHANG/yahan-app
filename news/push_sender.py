import json
import logging

from django.conf import settings

from django.db.models import Q

from django.utils import timezone

from pywebpush import (
    webpush,
    WebPushException,
)

from .models import (
    NewsPushSubscription,
    NewsPushBatch,
)


logger = logging.getLogger(__name__)


# =========================================================
# Send News Push
# =========================================================

def send_news_push_for_batch(
    batch_key,
    new_articles_count,
    user_id=None,
    is_test=False,
    headline="",
    subscriptions=None,
    title=None,
    body=None,
    url="/news/",
):
    """
    ニュース更新完了後にPushを送信する。

    通常送信:
        新着記事がある場合のみ、
        全登録ユーザーに送信する。

    テスト送信:
        指定したユーザーにのみ送信する。
    """

    # =====================================================
    # Validate
    # =====================================================

    if is_test and user_id is None:

        raise ValueError(
            "Test push requires user_id."
        )

    if not is_test and new_articles_count <= 0:

        return {
            "sent": 0,
            "reason": "No new articles.",
        }

    if not batch_key:

        raise ValueError(
            "batch_key is required."
        )

    if not all([

        settings.VAPID_PUBLIC_KEY,

        settings.VAPID_PRIVATE_KEY,

        settings.VAPID_CONTACT_EMAIL,

    ]):

        raise ValueError(
            "VAPID settings are missing."
        )

    # =====================================================
    # Subscription queryset
    # =====================================================

    if subscriptions is None:

        subscriptions = NewsPushSubscription.objects.all()

    subscriptions = subscriptions.filter(
        Q(user__isnull=True)
        | Q(user__is_active=True)
    )

    if user_id is not None:

        subscriptions = subscriptions.filter(
            user_id=user_id
        )

    if not subscriptions.exists():

        return {
            "sent": 0,
            "reason": "No subscribers.",
        }

    # =====================================================
    # Prevent duplicate batches
    # =====================================================

    batch = None

    if not is_test:

        batch, created = (

            NewsPushBatch.objects.get_or_create(

                batch_key=batch_key

            )

        )

        if not created:

            logger.info(
                "News Push already attempted: %s",
                batch_key,
            )

            return {
                "sent": 0,
                "reason": "Already attempted.",
            }

    # =====================================================
    # Notification payload
    # =====================================================

    if is_test:

        title = "Swiss News テスト通知"

        body = (
            "Push通知の設定が完了したよ！"
        )

    elif title and body:

        pass

    else:

        title = title or (
            "🇨🇭 スイスニュースが更新されたよ！"
        )

        if headline and new_articles_count > 1:

            body = (
                f"{headline}\n"
                f"ほか{new_articles_count - 1}件の新着ニュース"
            )

        elif headline:

            body = headline

        else:

            body = (
                f"新しいニュースが"
                f"{new_articles_count}件届いたよ 📰"
            )

    payload = json.dumps(

        {

            "title": title,

            "body": body,

            "batch_id": batch_key,

            "url": url,

        },

        ensure_ascii=False,

    )

    # =====================================================
    # Send
    # =====================================================

    sent_count = 0

    failed_count = 0

    try:

        for subscription in subscriptions.iterator():

            try:

                webpush(

                    subscription_info={

                        "endpoint": (
                            subscription.endpoint
                        ),

                        "keys": {

                            "p256dh": (
                                subscription.p256dh
                            ),

                            "auth": (
                                subscription.auth
                            ),

                        },

                    },

                    data=payload,

                    vapid_private_key=(
                        settings.VAPID_PRIVATE_KEY
                    ),

                    vapid_claims={

                        "sub": (
                            "mailto:"
                            + settings.VAPID_CONTACT_EMAIL
                        ),

                    },

                    ttl=3600,

                    timeout=5,

                )

                sent_count += 1

            except WebPushException as exc:

                failed_count += 1

                response = exc.response

                status_code = (

                    response.status_code

                    if response is not None

                    else None

                )

                # Invalid or expired subscription

                if status_code in (404, 410):

                    subscription.delete()

                logger.warning(

                    "News Push failed: "
                    "subscription=%s status=%s",

                    subscription.pk,

                    status_code,

                )

            except Exception:

                failed_count += 1

                logger.exception(

                    "Unexpected News Push error: "
                    "subscription=%s",

                    subscription.pk,

                )

    finally:

        if batch is not None:

            batch.sent_count = sent_count

            batch.failed_count = failed_count

            batch.completed_at = (
                timezone.now()
            )

            batch.save(

                update_fields=[

                    "sent_count",

                    "failed_count",

                    "completed_at",

                ]

            )

    logger.info(

        "News Push completed: "
        "batch=%s sent=%s failed=%s",

        batch_key,

        sent_count,

        failed_count,

    )

    return {

        "sent": sent_count,

        "failed": failed_count,

    }

# =========================================================
# Scheduled pushes (after each refresh)
# =========================================================

# 暮らしのお知らせを全員に届ける「スイス全国」の地域
NATIONWIDE_REGION_SLUG = "switzerland"

DAILY_PERIOD = "morning"

DAILY_WINDOW_HOURS = 24


def _top_headline(articles):
    """
    一番多くの媒体が報じた記事の見出し。
    """

    from news.services.deduplicator import (
        with_source_count,
    )

    top_article = (
        with_source_count(
            articles
        )
        .order_by(
            "-source_count",
            "-published_at",
        )
        .first()
    )

    return (
        top_article.title_ja
        if top_article
        else ""
    )


def _new_root_articles(since):

    from news.services.deduplicator import (
        ready_articles,
    )

    return (
        ready_articles()
        .filter(
            fetched_at__gte=since,
            duplicate_of__isnull=True,
        )
    )


def send_scheduled_pushes(
    period,
    started_at,
):
    """
    定時更新のあとに送る通知。

    every: 更新のたびに新着をお知らせ
    daily: 朝の更新のときだけ、24時間分をまとめてお知らせ
    暮らしのお知らせ: 地域を選んだ端末に、その地域と全国の分だけ
    """

    from datetime import timedelta

    today = timezone.localdate()

    results = {}

    # ---------------------------------------------
    # 更新のたび
    # ---------------------------------------------

    new_articles = _new_root_articles(
        started_at
    )

    results["every"] = send_news_push_for_batch(
        batch_key=f"{today:%Y-%m-%d}-{period}",
        new_articles_count=new_articles.count(),
        headline=_top_headline(new_articles),
        subscriptions=NewsPushSubscription.objects.filter(
            frequency="every",
        ),
    )

    # ---------------------------------------------
    # 1日1回（朝）
    # ---------------------------------------------

    if period == DAILY_PERIOD:

        day_articles = _new_root_articles(
            timezone.now()
            - timedelta(hours=DAILY_WINDOW_HOURS)
        )

        count = day_articles.count()

        headline = _top_headline(
            day_articles
        )

        results["daily"] = send_news_push_for_batch(
            batch_key=f"{today:%Y-%m-%d}-daily",
            new_articles_count=count,
            subscriptions=NewsPushSubscription.objects.filter(
                frequency="daily",
            ),
            title="🇨🇭 今日のスイスニュース",
            body=(
                f"{headline}\nほか{count - 1}件のニュースがあります"
                if headline and count > 1
                else headline
                or f"この24時間のニュースが{count}件あります"
            ),
        )

    # ---------------------------------------------
    # 暮らしのお知らせ
    # ---------------------------------------------

    results["life"] = send_life_alerts(
        period,
        started_at,
    )

    return results


def send_life_alerts(
    period,
    started_at,
):
    """
    暮らしのお知らせ（スト・運休・締め切りなど）を、
    地域を選んだ端末に送る。届くのはその地域と全国の分だけ。
    """

    alerts = list(
        _new_root_articles(
            started_at
        )
        .filter(
            life_alert=True,
        )
        .prefetch_related(
            "regions",
        )
        .order_by(
            "-published_at",
        )
    )

    if not alerts:

        return {
            "sent": 0,
            "reason": "No life alerts.",
        }

    # 同じ地域の組み合わせを選んだ端末には、同じ通知をまとめて送る
    groups = {}

    for subscription in (
        NewsPushSubscription.objects
        .filter(
            alert_regions__isnull=False,
        )
        .distinct()
        .prefetch_related(
            "alert_regions",
        )
    ):

        regions = tuple(
            sorted(
                subscription.alert_regions.all(),
                key=lambda region: region.pk,
            )
        )

        groups.setdefault(
            regions,
            [],
        ).append(
            subscription.pk
        )

    today = timezone.localdate()

    sent = 0

    for regions, subscription_ids in groups.items():

        region_ids = {
            region.pk
            for region in regions
        }

        matching = []
        matched_names = []

        for article in alerts:

            article_regions = list(
                article.regions.all()
            )

            local = [
                region
                for region in article_regions
                if region.pk in region_ids
            ]

            nationwide = any(
                region.slug == NATIONWIDE_REGION_SLUG
                for region in article_regions
            )

            if not local and not nationwide:
                continue

            matching.append(
                article
            )

            for region in local:
                if region.name not in matched_names:
                    matched_names.append(region.name)

            if nationwide and "スイス全国" not in matched_names:
                matched_names.append("スイス全国")

        if not matching:
            continue

        first = matching[0]

        body = first.title_ja or first.title_original

        if len(matching) > 1:
            body += f"\nほか{len(matching) - 1}件"

        group_key = "-".join(
            str(region.pk)
            for region in regions
        )

        result = send_news_push_for_batch(
            batch_key=(
                f"{today:%Y-%m-%d}-{period}-life-{group_key}"
            )[:150],
            new_articles_count=len(matching),
            subscriptions=NewsPushSubscription.objects.filter(
                pk__in=subscription_ids,
            ),
            title=(
                "📌 暮らしのお知らせ"
                f"（{'・'.join(matched_names)}）"
            ),
            body=body,
            url=(
                f"/news/a/{first.pk}/"
                if len(matching) == 1
                else "/news/life/"
            ),
        )

        sent += result.get("sent", 0)

    return {
        "sent": sent,
        "alerts": len(alerts),
    }
