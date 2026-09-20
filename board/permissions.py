# =========================================================
# Board permissions
# =========================================================

def can_post_board(user):

    """
    掲示板への投稿権限。

    ・Superuser
    ・board.add_boardpost 権限を持つユーザー
    """

    if not user.is_authenticated:
        return False

    return (
        user.is_superuser
        or user.has_perm(
            "board.add_boardpost"
        )
    )


def can_manage_post(user, post):

    """
    投稿を編集・削除できるか。

    ・Superuser は全投稿
    ・投稿権限を持つユーザーは自分の投稿
    """

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return (
        can_post_board(user)
        and post.author_id == user.pk
    )


def can_delete_comment(user, comment):

    """
    コメントを削除できるか。

    ・Superuser は全コメント
    ・一般ユーザーは自分のコメントのみ
    """

    if not user.is_authenticated:
        return False

    return (
        user.is_superuser
        or comment.author_id == user.pk
    )