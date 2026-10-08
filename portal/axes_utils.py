from django.contrib.auth import get_user_model


User = get_user_model()


def canonical_login_identifier(
    request,
    credentials,
):

    identifier = (
        credentials.get(
            "username",
            "",
        )
        .strip()
    )

    if not identifier:
        return ""

    # =====================================================
    # Username
    # =====================================================

    user = (
        User.objects
        .filter(
            username__iexact=identifier
        )
        .first()
    )

    if user is not None:

        return (
            user.username
            .strip()
            .lower()
        )

    # =====================================================
    # Email
    # =====================================================

    email_users = (
        User.objects
        .filter(
            email__iexact=identifier
        )
    )

    if email_users.count() == 1:

        user = email_users.first()

        return (
            user.username
            .strip()
            .lower()
        )

    # =====================================================
    # Unknown identifier
    # =====================================================

    return identifier.lower()