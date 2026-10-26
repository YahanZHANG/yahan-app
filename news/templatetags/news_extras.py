from datetime import timedelta

from django import template
from django.conf import settings
from django.utils import timezone


register = template.Library()


WEEKDAYS_JA = "月火水木金土日"


@register.simple_tag
def vapid_public_key():
    return getattr(
        settings,
        "VAPID_PUBLIC_KEY",
        "",
    )


@register.simple_tag
def latest_announcement():
    """
    表示中の最新のお知らせ（なければ None）。
    SHOW_DAYS を過ぎたものは自動で出なくなる。
    """

    from news.models import NewsAnnouncement

    since = timezone.now() - timedelta(
        days=NewsAnnouncement.SHOW_DAYS,
    )

    return (
        NewsAnnouncement.objects
        .filter(
            is_active=True,
            created_at__gte=since,
        )
        .first()
    )


@register.filter
def day_label(value):
    """
    記事一覧の日付見出し。
    今日 / 昨日 / 10月17日（金）
    """

    if not value:
        return ""

    day = timezone.localtime(
        value
    ).date()

    today = timezone.localdate()

    if day == today:
        return "今日"

    if day == today - timedelta(days=1):
        return "昨日"

    return (
        f"{day.month}月{day.day}日"
        f"（{WEEKDAYS_JA[day.weekday()]}）"
    )


@register.simple_tag(takes_context=True)
def absolute_url(context, path):
    """
    Facebook・LINE のプレビュー用に、https から始まる完全なURLを返す。
    Render はプロキシの後ろなので、本番では https に固定する。
    """

    request = context.get("request")

    if request is None:
        return path

    scheme = (
        "http"
        if settings.DEBUG
        else "https"
    )

    return f"{scheme}://{request.get_host()}{path}"


@register.simple_tag
def alert_region_choices():
    """
    暮らしのお知らせで選べる地域。
    """

    from news.push_views import alert_regions

    return list(
        alert_regions()
    )
