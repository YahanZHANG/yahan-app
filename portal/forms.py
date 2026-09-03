from django import forms

from travel.models import UserProfile


class NicknameForm(forms.ModelForm):

    nickname = forms.CharField(
        max_length=30,
        required=True,
        label="ニックネーム",
        widget=forms.TextInput(
            attrs={
                "class": "portal-nickname-input",
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
        nickname = self.cleaned_data["nickname"].strip()

        if not nickname:
            raise forms.ValidationError(
                "ニックネームを入力してください。"
            )

        return nickname