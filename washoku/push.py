"""
コメントに返信が来たこと、毎週月曜の「今週」のお知らせを、登録した端末にプッシュ通知で知らせる。
送信の仕組み (VAPID の鍵、Service Worker) は Swiss News と共通。
"""

import json
import logging

from django.conf import settings

from pywebpush import WebPushException, webpush

from .models import PushSubscription


logger = logging.getLogger(__name__)


def is_configured():
    return all(
        [
            settings.VAPID_PUBLIC_KEY,
            settings.VAPID_PRIVATE_KEY,
            settings.VAPID_CONTACT_EMAIL,
        ]
    )


def send_push(user_ids, title, body, url, tag):
    """
    指定した会員の端末すべてに送る。送れた件数を返す。
    送れなくても、コメントの投稿は止めない。
    """

    if not user_ids:
        return 0

    sent, _failed = send_to(PushSubscription.objects.filter(user_id__in=user_ids), title, body, url, tag)
    return sent


def send_to(subscriptions, title, body, url, tag):
    """
    登録した端末に送る。(送れた件数, 送れなかった端末の [(pk, HTTP ステータス)]) を返す。
    期限切れ・解除済みの端末 (404 / 410) は消す。
    """

    if not is_configured():
        return 0, []

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "url": url,
            "tag": tag,
        },
        ensure_ascii=False,
    )

    sent = 0
    failed = []

    for subscription in subscriptions:

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": "mailto:" + settings.VAPID_CONTACT_EMAIL,
                },
                ttl=86400,
                timeout=5,
            )
            sent += 1

        except WebPushException as error:

            status = error.response.status_code if error.response is not None else None
            failed.append((subscription.pk, status))

            if status in (404, 410):
                subscription.delete()

            logger.warning("和食の Push 送信に失敗: subscription=%s status=%s", subscription.pk, status)

        except Exception:
            failed.append((subscription.pk, None))
            logger.exception("和食の Push 送信で予期しないエラー: subscription=%s", subscription.pk)

    return sent, failed


def send_reply_push(comment, recipient_ids):
    """
    返信が付いたことを知らせる。質問した本人には「答えが来た」と伝える。
    """

    from .templatetags.washoku_tags import display_name

    root = comment.parent
    actor = display_name(comment.author)
    body = f"{actor}さん: {comment.body[:80]}"
    url = comment.get_absolute_url()
    tag = f"washoku-comment-{comment.pk}"

    asker = {root.author_id} if root.kind == "question" else set()
    others = set(recipient_ids) - asker

    send_push(
        asker & set(recipient_ids),
        f"質問に答えが届きました（{root.target.name}）",
        body,
        url,
        tag,
    )

    send_push(
        others,
        f"コメントに返信がありました（{root.target.name}）",
        body,
        url,
        tag,
    )


def send_stamp_push(recipient_id, actor_user, label, target_text, url, tag):
    """
    コメントやコラムにスタンプが押されたことを知らせる。
    """

    from .templatetags.washoku_tags import display_name

    send_push(
        {recipient_id},
        f"{display_name(actor_user)}さんが「{label}」を押しました",
        target_text[:80],
        url,
        tag,
    )
