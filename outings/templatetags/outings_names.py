
from django import template
from django.core.exceptions import ObjectDoesNotExist


register = template.Library()


@register.filter
def outings_display_name(user):
    """
    Return the Yapp nickname for a comment author.

    If the nickname cannot be found, display 'ユーザー'.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return "ユーザー"

    # Nickname stored directly on the User model.
    nickname = getattr(user, "nickname", None)

    if isinstance(nickname, str) and nickname.strip():
        return nickname.strip()

    # Common profile relationship names.
    for relation_name in (
        "profile",
        "userprofile",
        "portalprofile",
    ):
        try:
            profile = getattr(user, relation_name, None)
        except ObjectDoesNotExist:
            continue

        if profile is None:
            continue

        nickname = getattr(profile, "nickname", None)

        if isinstance(nickname, str) and nickname.strip():
            return nickname.strip()

    # Other OneToOne profile relationships.
    for relation in user._meta.related_objects:
        if not relation.one_to_one:
            continue

        relation_name = relation.get_accessor_name()

        try:
            profile = getattr(user, relation_name, None)
        except ObjectDoesNotExist:
            continue

        if profile is None:
            continue

        nickname = getattr(profile, "nickname", None)

        if isinstance(nickname, str) and nickname.strip():
            return nickname.strip()

    return "ユーザー"
