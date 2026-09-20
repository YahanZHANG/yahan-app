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

        }


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