from django import forms

from .models import Comment, Feedback


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


class FeedbackForm(forms.ModelForm):

    # 人には見えない項目。全部の項目を埋めるボットだけが入力する。
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "tabindex": "-1",
                "autocomplete": "off",
                "class": "washoku-trap",
                "aria-hidden": "true",
            }
        ),
    )

    class Meta:
        model = Feedback
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "maxlength": 1000,
                    "placeholder": "ご自由にお書きください（1000文字まで）",
                }
            ),
        }

    def clean_message(self):

        message = self.cleaned_data["message"].strip()

        if not message:
            raise forms.ValidationError("内容を入力してください。")

        return message
