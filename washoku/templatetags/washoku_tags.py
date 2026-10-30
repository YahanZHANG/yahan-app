from django import template
from django.conf import settings

from washoku.models import Notification


register = template.Library()


@register.filter
def display_name(user):
    """
    Yapp のニックネーム。プロフィールがなければユーザー名。
    """

    if user is None:
        return "退会した会員"

    try:
        return user.profile.display_name
    except Exception:
        return user.username


@register.simple_tag(takes_context=True)
def unread_notification_count(context):

    user = context["request"].user

    if not user.is_authenticated:
        return 0

    return Notification.objects.filter(
        recipient=user,
        is_read=False,
    ).count()


@register.filter
def stars(value):
    """
    3.5 -> ★★★☆☆ (四捨五入)
    """

    if value is None:
        return ""

    filled = int(round(float(value)))

    return "★" * filled + "☆" * (5 - filled)


@register.simple_tag
def search_engines_allowed():
    return getattr(settings, "WASHOKU_ALLOW_SEARCH_ENGINES", False)


@register.filter
def thumb(url, size=160):
    """Cloudinary の写真なら小さく切り抜いた版にする。"""
    from ..photos import thumbnail_url
    return thumbnail_url(url, int(size))


@register.simple_tag
def vapid_public_key():
    """プッシュ通知の公開鍵 (未設定なら空)"""

    return settings.VAPID_PUBLIC_KEY or ""


@register.filter(is_safe=True, needs_autoescape=True)
def linkify(value, autoescape=True):
    """
    本文の URL をリンクにする (新しいタブで開く)。そのあと linebreaks / linebreaksbr を付けて使う。
    """

    from django.utils.html import urlize
    from django.utils.safestring import mark_safe

    html = urlize(str(value), trim_url_limit=60, nofollow=True, autoescape=autoescape)
    return mark_safe(html.replace('rel="nofollow"', 'rel="nofollow noopener" target="_blank"'))
