from django import forms

from .models import (
    Event,
    EventDate,
)


# =========================================================
# Event
# =========================================================

class EventForm(forms.ModelForm):

    class Meta:

        model = Event

        fields = [
            "title",
            "description",
            "location",
            "is_public",
            "allow_participant_date_addition",
            "allow_participant_time_option_addition",
            "scheduling_mode",
            "duration_mode",
            "duration_minutes",
            "allow_participant_duration_addition",
            "response_deadline",
        ]

        widgets = {

            "title":
                forms.TextInput(
                    attrs={
                        "placeholder":
                            "例：10月の飲み会",
                    }
                ),

            "description":
                forms.Textarea(
                    attrs={
                        "rows":
                            4,

                        "placeholder":
                            "イベントについての説明",
                    }
                ),

            "location":
                forms.TextInput(
                    attrs={
                        "placeholder":
                            "例：Zürich HB周辺",
                    }
                ),

            "scheduling_mode":
                forms.RadioSelect(),

            "duration_mode":
                forms.RadioSelect(),

            "duration_minutes":
                forms.NumberInput(
                    attrs={
                        "min":
                            15,

                        "step":
                            15,

                        "placeholder":
                            "例：120",
                    }
                ),

            "response_deadline":
                forms.DateInput(
                    attrs={
                        "type":
                            "date",
                    }
                ),
        }

        labels = {

            "title":
                "イベント名",

            "description":
                "説明",

            "location":
                "場所",

            "is_public":
                "公開イベントにする",

            "allow_participant_date_addition":
                "参加者による候補日の追加を許可する",

            "allow_participant_time_option_addition":
                "参加者による時間帯の追加を許可する",

            "scheduling_mode":
                "日程の決め方",

            "duration_mode":
                "イベントの長さの決め方",

            "duration_minutes":
                "イベント時間（分）",

            "allow_participant_duration_addition":
                "参加者による長さ候補の追加を許可する",

            "response_deadline":
                "回答締切",
        }


# =========================================================
# Event date
# =========================================================

class EventDateForm(forms.ModelForm):

    class Meta:

        model = EventDate

        fields = [
            "date",
        ]

        widgets = {

            "date":
                forms.DateInput(
                    attrs={
                        "type":
                            "date",
                    }
                ),
        }

        labels = {

            "date":
                "候補日",
        }


# =========================================================
# Event date response
# =========================================================

class EventDateResponseForm(forms.Form):

    RESPONSE_CHOICES = [
        (
            "all_day",
            "終日OK",
        ),
        (
            "partial",
            "時間を指定",
        ),
        (
            "unavailable",
            "参加できない",
        ),
    ]

    response_type = forms.ChoiceField(
        choices=RESPONSE_CHOICES,
        widget=forms.RadioSelect,
        label="この日の予定",
    )

    note = forms.CharField(
        required=False,
        max_length=255,
        label="メモ",
        widget=forms.TextInput(
            attrs={
                "placeholder":
                    "例：できれば午後希望",
            }
        ),
    )


# =========================================================
# Event admin invitation
# =========================================================

class EventAdminInviteForm(forms.Form):

    username = forms.CharField(
        max_length=150,
        label="ログインID",
        widget=forms.TextInput(
            attrs={
                "placeholder":
                    "共同管理者のログインID",

                "autocomplete":
                    "off",
            }
        ),
    )


# =========================================================
# Event participant invitation
# =========================================================

class EventParticipantInviteForm(forms.Form):

    username = forms.CharField(
        max_length=150,
        label="ログインID",
        widget=forms.TextInput(
            attrs={
                "placeholder":
                    "招待する参加者のログインID",

                "autocomplete":
                    "off",
            }
        ),
    )