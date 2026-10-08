from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):

    def authenticate(
        self,
        request,
        username=None,
        password=None,
        **kwargs,
    ):

        if username is None:

            username = kwargs.get(
                User.USERNAME_FIELD
            )

        if (
            not username
            or password is None
        ):

            return None

        identifier = username.strip()

        # =================================================
        # 1. Username
        # =================================================

        user = (
            User.objects
            .filter(
                username__iexact=identifier
            )
            .order_by(
                "id"
            )
            .first()
        )

        # =================================================
        # 2. Email
        # =================================================

        if user is None:

            email_users = (
                User.objects
                .filter(
                    email__iexact=identifier
                )
                .order_by(
                    "id"
                )
            )

            # 既存データに同じメールアドレスが
            # 複数存在する場合はメールログインさせない
            if email_users.count() == 1:

                user = email_users.first()

            else:

                # Password hashingを実行して
                # timing差を小さくする
                dummy_user = User()
                dummy_user.set_password(
                    password
                )

                return None

        # =================================================
        # Password / active check
        # =================================================

        if (
            user.check_password(
                password
            )
            and self.user_can_authenticate(
                user
            )
        ):

            return user

        return None