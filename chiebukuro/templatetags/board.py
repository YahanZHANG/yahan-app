"""掲示板の表示用: 「3時間前」などの時間、アイコンの頭文字と色"""

from django import template
from django.utils import timezone


register = template.Library()


@register.filter
def ago(value):
    if not value:
        return ""
    now = timezone.now()
    seconds = (now - value).total_seconds()
    if seconds < 60:
        return "たった今"
    if seconds < 3600:
        return f"{int(seconds // 60)}分前"
    if seconds < 86400:
        return f"{int(seconds // 3600)}時間前"
    if seconds < 86400 * 7:
        return f"{int(seconds // 86400)}日前"
    local = timezone.localtime(value)
    if local.year == timezone.localtime(now).year:
        return f"{local.month}月{local.day}日"
    return f"{local.year}年{local.month}月{local.day}日"


@register.filter
def initial(name):
    name = (name or "").strip()
    return name[:1].upper() if name else "?"


@register.filter
def avatar(user_id):
    """ユーザーごとに決まった色 (8色)"""
    try:
        return f"cb-av{int(user_id or 0) % 8}"
    except (TypeError, ValueError):
        return "cb-av0"


def _board_profile(context, user):
    """1回の表示で同じ人のプロフィールを何度も読まないように、request にためておく"""

    from chiebukuro.models import BoardProfile

    request = context.get("request")
    cache = getattr(request, "_cb_faces", None) if request is not None else None
    if cache is None:
        cache = {}
        if request is not None:
            request._cb_faces = cache
    if user.pk not in cache:
        cache[user.pk] = BoardProfile.objects.filter(user_id=user.pk).only(
            "avatar_kind", "avatar_parts", "photo_url"
        ).first()
    return cache[user.pk]


@register.simple_tag(takes_context=True)
def face(context, user, name=""):
    """アイコンの中身: 写真・イラスト・名前の1文字 (.cb-av の中に入れる)"""

    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    from chiebukuro import avatar as avatar_art

    profile = _board_profile(context, user) if getattr(user, "pk", None) else None
    if profile and profile.avatar_kind == "photo" and profile.photo_url:
        return mark_safe(f'<img src="{escape(profile.photo_url)}" alt="" loading="lazy">')
    if profile and profile.avatar_kind == "illust":
        return mark_safe(avatar_art.svg(profile.avatar_parts))
    return initial(name)
