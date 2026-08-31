from django.db.models import Q

from .models import (
    Child,
    ChildCollaborator,
)


def get_accessible_children(user):
    """
    自分の子ども +
    他ユーザーから共有された子ども。
    """

    return (
        Child.objects
        .filter(
            Q(owner=user)
            |
            Q(
                collaborators__user=user
            )
        )
        .distinct()
    )


def user_can_view_child(
    user,
    child,
):
    if child.owner_id == user.id:
        return True

    return (
        ChildCollaborator.objects
        .filter(
            child=child,
            user=user,
        )
        .exists()
    )


def user_can_edit_child(
    user,
    child,
):
    if child.owner_id == user.id:
        return True

    return (
        ChildCollaborator.objects
        .filter(
            child=child,
            user=user,
            permission=(
                ChildCollaborator
                .PERMISSION_EDIT
            ),
        )
        .exists()
    )


def user_can_manage_child(
    user,
    child,
):
    """
    共同管理者の追加・削除は
    子どもの所有者だけ。
    """

    return (
        child.owner_id
        == user.id
    )