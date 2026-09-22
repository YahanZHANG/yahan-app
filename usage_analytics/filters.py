from django.contrib.auth import get_user_model


DEFAULT_EXCLUDED_USERNAMES = (
    "admin",
    "yahan",
    "fumimasakubo",
)


def get_excluded_user_ids(request):
    """
    初回表示:
        指定した3アカウントを除外。

    フィルター変更後:
        ユーザーが選んだ除外対象を優先。

    filter_applied=1 があれば、
    除外対象ゼロ件も明示的な選択として扱う。
    """

    User = get_user_model()

    has_explicit_filter = (
        "filter_applied" in request.GET
        or "exclude_users" in request.GET
    )

    if has_explicit_filter:

        selected_ids = [
            int(value)
            for value in request.GET.getlist("exclude_users")
            if value.isdecimal()
        ]

        return list(
            User.objects.filter(
                pk__in=selected_ids
            ).values_list(
                "pk",
                flat=True,
            )
        )

    return list(
        User.objects.filter(
            username__in=DEFAULT_EXCLUDED_USERNAMES
        ).values_list(
            "pk",
            flat=True,
        )
    )