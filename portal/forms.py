from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)

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
            "メール確認がまだの場合は、"
            "確認メール内のリンクを開いてください。"
        ),
        "inactive": (
            "このアカウントは現在利用できません。"
        ),
    }


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