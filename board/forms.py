from django import forms

from .models import (
    BoardPost,
    BoardComment,
)


# =========================================================
# Post form
# =========================================================

class BoardPostForm(forms.ModelForm):

    class Meta:

        model = BoardPost

        fields = [
            "title",
            "body",
            "is_pinned",
            "audience_type",
            "audience_users",
        ]

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "class": "board-input",
                    "placeholder": "お知らせのタイトル",
                }
            ),

            "body": forms.Textarea(
                attrs={
                    "class": "board-textarea",
                    "placeholder": "お知らせの内容を書く...",
                    "rows": 7,
                }
            ),

            "is_pinned": forms.CheckboxInput(
                attrs={
                    "class": "board-checkbox",
                }
            ),

            "audience_type": forms.Select(
                attrs={
                    "class": "board-input",
                }
            ),

            "audience_users": forms.CheckboxSelectMultiple(),

        }


    def clean(self):

        cleaned_data = super().clean()

        audience_type = cleaned_data.get(
            "audience_type"
        )

        audience_users = cleaned_data.get(
            "audience_users"
        )


        # 全ユーザーの場合は対象ユーザーを空にする
        if (
            audience_type
            == BoardPost.AudienceType.ALL
        ):

            cleaned_data[
                "audience_users"
            ] = self.fields[
                "audience_users"
            ].queryset.none()


        # 指定方式なら最低1人必要
        elif (
            audience_type
            in [
                BoardPost.AudienceType.INCLUDE,
                BoardPost.AudienceType.EXCLUDE,
            ]
            and not audience_users
        ):

            self.add_error(
                "audience_users",
                "対象ユーザーを1人以上選択してください。",
            )


        return cleaned_data

# =========================================================
# Comment form
# =========================================================

class BoardCommentForm(forms.ModelForm):

    class Meta:

        model = BoardComment

        fields = [
            "body",
        ]

        widgets = {

            "body": forms.Textarea(
                attrs={
                    "class": "board-textarea",
                    "placeholder": "コメントを書く...",
                    "rows": 3,
                }
            ),

        }

        labels = {
            "body": "コメント",
        }