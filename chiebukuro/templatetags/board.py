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
