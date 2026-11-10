"""
掲示板のプッシュ通知。
送る仕組み (VAPID の鍵・Service Worker・送信) は Swiss News・和食と共通 (washoku.push.send_to)。

- 「すぐに」の人: お知らせができたとき、その種類がオンなら1件ずつ送る
- 「1日1回」の人: 毎日19時 (スイス時間) に、その日の未読の数をまとめて1回だけ送る
"""

import logging
import threading
from datetime import timedelta

from django.utils import timezone


logger = logging.getLogger(__name__)

DIGEST_HOUR = 19

# お知らせの種類 → プロフィールのオン・オフの項目
KIND_SETTING = {
    "answer": "push_answer",
    "reply": "push_reply",
    "stamp": "push_stamp",
    "talk": "push_talk",
    "chosen": "push_talk",
}


def wants(profile, kind):
    field = KIND_SETTING.get(kind)
    return bool(field and getattr(profile, field, False))


def send(devices, title, body, url, tag):
    from washoku.push import is_configured, send_to

    if not is_configured():
        return 0
    sent, _failed = send_to(devices, title, body, url, tag)
    return sent


def push_notification(notification):
    """お知らせ1件を、すぐに知らせる設定の人へ (別スレッドで。失敗しても書き込みは止めない)"""

    from washoku.push import is_configured

    from .models import BoardProfile, PushDevice

    if not is_configured():
        return
    profile = BoardProfile.objects.filter(user_id=notification.user_id).first()
    frequency = profile.push_frequency if profile else BoardProfile.PushFrequency.INSTANT
    if frequency != BoardProfile.PushFrequency.INSTANT:
        return
    if not wants(profile or BoardProfile(), notification.kind):
        return
    devices = list(PushDevice.objects.filter(user_id=notification.user_id))
    if not devices:
        return
    body = (f"{notification.actor}さん：" if notification.actor else "") + notification.text

    def run():
        try:
            send(devices, "スイス掲示板", body, notification.url, f"chiebukuro-{notification.kind}")
        except Exception:
            logger.exception("掲示板の Push 送信に失敗")

    threading.Thread(target=run, daemon=True).start()


def send_daily_digest(now=None):
    """1日1回の人に、この24時間の未読のお知らせの数を送る。送った人数を返す。"""

    from .models import BoardProfile, Notification, PushDevice

    now = now or timezone.now()
    since = now - timedelta(days=1)
    people = 0
    for profile in BoardProfile.objects.filter(push_frequency=BoardProfile.PushFrequency.DAILY):
        kinds = [kind for kind in KIND_SETTING if wants(profile, kind)]
        count = Notification.objects.filter(
            user_id=profile.user_id, read_at__isnull=True, created_at__gte=since, kind__in=kinds
        ).count()
        devices = list(PushDevice.objects.filter(user_id=profile.user_id))
        if not count or not devices:
            continue
        if send(devices, "スイス掲示板", f"未読のお知らせが{count}件あります", "/swiss-board/notifications/", "chiebukuro-digest"):
            people += 1
    return people


def run_if_due(state_dir, now=None, write=print):
    """
    毎日19時を過ぎていて、今日まだ送っていなければ送る (1分ごとに呼ばれる前提)。
    日曜はあわせて「今週のありがとう」のまとめも (services.send_weekly_thanks)。
    """

    now = now or timezone.now()
    local = timezone.localtime(now)
    if local.hour < DIGEST_HOUR:
        return False
    week_marker = state_dir / f"{local.strftime('%Y-%m-%d')}.chiebukuro-week"
    if local.weekday() == 6 and not week_marker.exists():
        from .services import send_weekly_thanks

        state_dir.mkdir(parents=True, exist_ok=True)
        week_marker.write_text(now.isoformat(), encoding="utf-8")
        try:
            write(f"Board weekly thanks: {send_weekly_thanks(now)} people")
        except Exception:
            logger.exception("週のまとめに失敗")
    marker = state_dir / f"{local.strftime('%Y-%m-%d')}.chiebukuro-digest"
    if marker.exists():
        return False
    state_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text(now.isoformat(), encoding="utf-8")
    write(f"Board daily digest: sent to {send_daily_digest(now)} people")
    return True
