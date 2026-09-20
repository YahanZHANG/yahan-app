from django import template

from travel.models import UserProfile


register = template.Library()


@register.filter
def board_name(user):

    if not user:
        return ""

    nickname = (
        UserProfile.objects
        .filter(user=user)
        .values_list(
            "nickname",
            flat=True,
        )
        .first()
    )

    return (
        nickname
        or user.get_username()
    )