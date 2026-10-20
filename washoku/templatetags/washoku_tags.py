from django import template
from django.conf import settings

from washoku.models import Notification


register = template.Library()


@register.filter
def display_name(user):
    """
    Yapp のニックネーム。プロフィールがなければユーザー名。
    """

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
