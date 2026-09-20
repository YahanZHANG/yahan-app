import json
import logging

from django.conf import settings

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

    subscriptions = (

        NewsPushSubscription.objects
        .filter(
            user__is_active=True
        )

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

        title = "Yahan News テスト通知"

        body = (
            "Push通知の設定が完了したよ！"
        )

    else:

        title = (
            "🇨🇭 スイスニュースが更新されたよ！"
        )

        body = (
            f"新しいニュースが"
            f"{new_articles_count}件届いたよ 📰"
        )

    payload = json.dumps(

        {

            "title": title,

            "body": body,

            "batch_id": batch_key,

            "url": "/news/",

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