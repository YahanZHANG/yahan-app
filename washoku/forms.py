from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):

    class Meta:
        model = Comment
        fields = ["kind", "body"]
        widgets = {
            "kind": forms.RadioSelect,
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "maxlength": 500,
                    "placeholder": "スイスで作るときの工夫や、食材の買い方など",
                }
            ),
        }


class CommentEditForm(forms.ModelForm):

    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 500,
                }
            ),
        }
