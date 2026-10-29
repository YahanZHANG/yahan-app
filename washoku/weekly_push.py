"""
毎週月曜16時の「今週」のお知らせ (プッシュ通知)。
先週のアンケートの結果と、今週のアンケートが始まったことを知らせる。

Render では Outings のスケジューラー (1分ごとに起きる) から run_if_due を呼ぶ。
同じ週に2回送らないよう、送る前に目印のファイルを置く。
手で試すときは: python manage.py washoku_weekly_push --dry-run
"""

import logging

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.utils import timezone

from .models import DisplaySettings, Post, PushSubscription
from .push import send_to


logger = logging.getLogger(__name__)

WEEKDAY = 0          # 月曜日
SEND_HOUR = 16       # 夕方、晩ごはんを考えはじめるころ
LAST_HOUR = 21       # 再起動などで遅れても、夜遅くには送らない (その週は送らない)
URL = "/washoku/?tab=week"
TITLE_MAX = 40
BODY_MAX = 140


def shorten(text, limit):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def top_answer(poll):
    """先週のアンケートの1位を「〇〇」が1位（N%）の形で。票がなければ空"""

    results = poll.results

    if results["type"] == "text":
        return f"{results['total']}件の答えが集まりました。" if results["total"] else ""

    top = [row for row in results["choices"] if row["top"]]

    if not top:
        return ""

    names = "」「".join(shorten(row["choice"].label, 20) for row in top[:3])
    rank = "同率1位" if len(top) > 1 else "1位"
    return f"「{names}」が{rank}（{top[0]['percent']}%）でした。"


def weekly_message(now=None):
    """(タイトル, 本文) を返す。知らせることがない週は None"""

    from .views import last_week_polls, poll_posts_q, poll_week_start

    week_start = poll_week_start(now)

    request = HttpRequest()
    request.user = AnonymousUser()

    last = last_week_polls(request, week_start)
    last_text = ""

    if last and last[0].results["total"]:
        answer = top_answer(last[0])
        if answer:
            last_text = f"先週の「{shorten(last[0].poll_title, 30)}」は{answer}"

    new_poll = (
        Post.objects
        .filter(status="published", created_at__gte=week_start)
        .filter(poll_posts_q())
        .order_by("-created_at", "-pk")
        .first()
    )

    lines = []

    if last_text:
        lines.append(last_text)

    if new_poll:
        lines.append(f"今週のアンケートは「{shorten(new_poll.poll_title, 40)}」です。")
        title = "今週のアンケートが始まりました"
    elif last_text:
        title = "先週のアンケートの結果が出ました"
    else:
        message = DisplaySettings.load().weekly_message.strip()
        if not message:
            return None
        title = "今週のスイスで和食"
        lines.append(message)

    return shorten(title, TITLE_MAX), shorten("".join(lines), BODY_MAX)


def send_weekly_push(now=None):
    """「今週」のお知らせを受け取る端末すべてに送る。送れた件数を返す (送るものがなければ None)"""

    message = weekly_message(now)

    if message is None:
        return None

    title, body = message
    week = timezone.localtime(now or timezone.now()).strftime("%G-W%V")

    sent, _failed = send_to(
        PushSubscription.objects.filter(weekly=True),
        title,
        body,
        URL,
        f"washoku-weekly-{week}",
    )
    return sent


def due(now):
    local = timezone.localtime(now)
    return local.weekday() == WEEKDAY and SEND_HOUR <= local.hour < LAST_HOUR


def run_if_due(state_dir, now=None, write=print):
    """
    月曜16時を過ぎていて、今週まだ送っていなければ送る。
    1分ごとに呼ばれる前提。送った (送ろうとした) ら True。
    """

    now = now or timezone.now()

    if not due(now):
        return False

    marker = state_dir / f"{timezone.localtime(now).strftime('%G-W%V')}.washoku-weekly-push"

    if marker.exists():
        return False

    # 送る途中で止まっても、同じ週に2回送らないよう先に置く
    state_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text(now.isoformat(), encoding="utf-8")

    sent = send_weekly_push(now)
    write(f"Washoku weekly push: {'nothing to send' if sent is None else f'sent to {sent} devices'}")
    return True
