VIEWER_GROUP_NAME = "利用状況閲覧者"


def can_view_analytics(user):

    if not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    if user.is_superuser:
        return True

    return user.groups.filter(
        name=VIEWER_GROUP_NAME
    ).exists()