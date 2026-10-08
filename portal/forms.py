from django import forms

from django.contrib.auth import get_user_model

from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)

from django.core.exceptions import ValidationError

from travel.models import UserProfile

from .models import PortalAppPreference


User = get_user_model()

class YappAuthenticationForm(
    AuthenticationForm
):

    username = forms.CharField(
        label=(
            "ユーザーIDまたは"
            "メールアドレス"
        ),
        widget=forms.TextInput(
            attrs={
                "placeholder": (
                    "ユーザーIDまたは"
                    "メールアドレス"
                ),
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )

    password = forms.CharField(
        label="パスワード",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "パスワード",
                "autocomplete": (
                    "current-password"
                ),
            }
        ),
    )

    error_messages = {
        "invalid_login": (
            "ユーザーIDまたはメールアドレス、"
            "パスワードを確認してください。"
        ),
        "inactive": (
            "このアカウントは現在利用できません。"
        ),
    }

    def _find_user(
        self,
        identifier,
    ):

        user = (
            User.objects
            .filter(
                username__iexact=identifier
            )
            .first()
        )

        if user is not None:
            return user

        email_users = (
            User.objects
            .filter(
                email__iexact=identifier
            )
        )

        if email_users.count() == 1:
            return email_users.first()

        return None


    def clean(self):

        try:

            return super().clean()

        except ValidationError as error:

            identifier = (
                self.cleaned_data.get(
                    "username",
                    "",
                )
                .strip()
            )

            password = (
                self.cleaned_data.get(
                    "password"
                )
            )

            if (
                identifier
                and password
            ):

                user = self._find_user(
                    identifier
                )

                if (
                    user is not None
                    and not user.is_active
                    and user.check_password(
                        password
                    )
                ):

                    raise ValidationError(
                        (
                            "メールアドレスの確認が"
                            "まだ完了していません。"
                            "確認メール内のリンクを開くか、"
                            "確認メールを再送してください。"
                        ),
                        code="inactive",
                    )

            raise error

class ResendVerificationForm(
    forms.Form
):

    email = forms.EmailField(
        label="メールアドレス",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "example@email.com",
                "autocomplete": "email",
            }
        ),
    )

    def clean_email(self):

        return (
            self.cleaned_data[
                "email"
            ]
            .strip()
            .lower()
        )


class SignupForm(UserCreationForm):

    email = forms.EmailField(
        required=True,
        label="メールアドレス",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "example@email.com",
                "autocomplete": "email",
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password1",
            "password2",
        ]

    def clean_username(self):

        username = (
            self.cleaned_data["username"]
            .strip()
        )

        if User.objects.filter(
            username__iexact=username
        ).exists():

            raise forms.ValidationError(
                "このユーザーIDはすでに使用されています。"
            )

        return username

    def clean_email(self):

        email = (
            self.cleaned_data["email"]
            .strip()
            .lower()
        )

        if User.objects.filter(
            email__iexact=email
        ).exists():

            raise forms.ValidationError(
                "このメールアドレスはすでに登録されています。"
            )

        return email


class NicknameForm(forms.ModelForm):

    nickname = forms.CharField(
        max_length=30,
        required=True,
        label="ニックネーム",
        widget=forms.TextInput(
            attrs={
                "class": "password-input",
                "placeholder": "ニックネームを入力",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = UserProfile
        fields = [
            "nickname",
        ]

    def clean_nickname(self):

        nickname = (
            self.cleaned_data[
                "nickname"
            ].strip()
        )

        if not nickname:

            raise forms.ValidationError(
                "ニックネームを入力してください。"
            )

        return nickname


class AppSelectionForm(forms.Form):

    apps = forms.MultipleChoiceField(
        label="表示するアプリ",
        choices=(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": (
                "少なくとも1つのアプリを"
                "選んでください。"
            ),
        },
    )

    def __init__(
        self,
        *args,
        choices=None,
        **kwargs,
    ):

        super().__init__(
            *args,
            **kwargs,
        )

        if choices is None:
            choices = (
                PortalAppPreference
                .AppKey
                .choices
            )

        self.fields[
            "apps"
        ].choices = choices


class ResendVerificationForm(forms.Form):

    email = forms.EmailField(
        label="メールアドレス",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "example@email.com",
                "autocomplete": "email",
            }
        ),
    )

    def clean_email(self):

        return (
            self.cleaned_data["email"]
            .strip()
            .lower()
        )