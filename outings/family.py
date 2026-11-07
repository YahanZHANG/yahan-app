"""家族: the same family as スイスで和食 (one Yapp account, one family).
Members see each other's お気に入り, 行った and 行ってみたい."""


def membership(user):
    if not user.is_authenticated:
        return None
    from washoku.models import HouseholdMember
    return HouseholdMember.objects.filter(user=user).select_related("household").first()


def members(user):
    """Everyone in the family, the visitor first; [] when not in a family."""
    mine = membership(user)
    if mine is None:
        return []
    others = [m.user for m in mine.household.members.select_related("user").exclude(user=user)]
    return [user] + others
