from django import forms

from .models import ChatMessage


class ChatMessageForm(forms.ModelForm):

    class Meta:

        model = ChatMessage

        fields = [
            "body",
        ]

        widgets = {

            "body": forms.Textarea(
                attrs={
                    "class": "chat-message-input",
                    "placeholder": (
                        "メッセージを入力..."
                    ),
                    "rows": 2,
                    "maxlength": 2000,
                    "required": True,
                }
            ),

        }

        labels = {
            "body": "",
        }

    def clean_body(self):

        body = (
            self.cleaned_data["body"].strip()
        )

        if not body:

            raise forms.ValidationError(
                "メッセージを入力してね。"
            )

        return body