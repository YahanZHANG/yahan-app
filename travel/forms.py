from django import forms
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import get_user_model

from .models import (
    BabyGrowthNote,
    BabyLog,
    Expense,
    FamilyStatus,
    MeetingNote,
    MilkLog,
    PoopLog,
    Schedule,
    SleepLog,
    Task,
)


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault("attrs", {})
        attrs.setdefault("step", "60")

        super().__init__(
            *args,
            format="%Y-%m-%dT%H:%M",
            **kwargs,
        )


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule

        fields = [
            "title",
            "person",
            "start_at",
            "end_at",
            "location",
            "note",
            "is_important",
        ]

        widgets = {
            "start_at": DateTimeLocalInput(),
            "end_at": DateTimeLocalInput(),
            "note": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task

        fields = [
            "title",
            "assigned_to",
            "due_at",
            "priority",
            "note",
        ]

        widgets = {
            "due_at": DateTimeLocalInput(),
            "note": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }


class BabyLogForm(forms.ModelForm):
    class Meta:
        model = BabyLog

        fields = [
            "log_type",
            "recorded_at",
            "amount",
            "unit",
            "note",
        ]

        widgets = {
            "recorded_at": DateTimeLocalInput(),
            "note": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound:
            self.fields["recorded_at"].initial = (
                timezone.localtime()
                .replace(second=0, microsecond=0)
                .strftime("%Y-%m-%dT%H:%M")
            )

class FamilyStatusForm(forms.ModelForm):
    class Meta:
        model = FamilyStatus

        fields = [
            "status",
            "message",
        ]

class MilkLogForm(forms.ModelForm):
    class Meta:
        model = MilkLog

        fields = [
            "fed_at",
            "amount_ml",
        ]

        widgets = {
            "fed_at": DateTimeLocalInput(
                attrs={
                    "data-default-now": "true",
                }
            ),
        }


class SleepLogForm(forms.ModelForm):
    class Meta:
        model = SleepLog

        fields = [
            "started_at",
            "ended_at",
        ]

        widgets = {
            "started_at": DateTimeLocalInput(),
            "ended_at": DateTimeLocalInput(
                attrs={
                    "data-default-now": "true",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        started_at = cleaned_data.get("started_at")
        ended_at = cleaned_data.get("ended_at")

        if started_at and ended_at and ended_at <= started_at:
            raise forms.ValidationError(
                "起床時刻は寝入り時刻より後にしてください。"
            )

        return cleaned_data

class PoopLogForm(forms.ModelForm):
    class Meta:
        model = PoopLog

        fields = [
            "happened_at",
            "amount",
            "note",
        ]

        widgets = {
            "happened_at": DateTimeLocalInput(
                attrs={
                    "data-default-now": "true",
                }
            ),
            "note": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }

class MeetingNoteForm(forms.ModelForm):
    class Meta:
        model = MeetingNote

        fields = [
            "discussed_at",
            "decisions",
            "next_actions",
        ]

        widgets = {
            "discussed_at": DateTimeLocalInput(
                attrs={
                    "data-default-now": "true",
                }
            ),
            "decisions": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": (
                        "例：\n"
                        "・明日は8時に出発\n"
                        "・ベビーカーはパパが担当"
                    ),
                }
            ),
            "next_actions": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "例：\n"
                        "・じいじがガソリンを確認\n"
                        "・ママがミルク用品を準備"
                    ),
                }
            ),
        }

class ExpenseForm(forms.ModelForm):
    """支出本体と4人分の負担額を入力するフォーム。"""

    papa_amount = forms.DecimalField(
        label="パパの負担額",
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        initial=Decimal("0"),
        widget=forms.NumberInput(
            attrs={
                "min": "0",
                "step": "0.01",
                "inputmode": "decimal",
                "class": "expense-share-input",
                "data-share-username": "papa",
            }
        ),
    )

    mama_amount = forms.DecimalField(
        label="ママの負担額",
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        initial=Decimal("0"),
        widget=forms.NumberInput(
            attrs={
                "min": "0",
                "step": "0.01",
                "inputmode": "decimal",
                "class": "expense-share-input",
                "data-share-username": "mama",
            }
        ),
    )

    yeye_amount = forms.DecimalField(
        label="じいじの負担額",
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        initial=Decimal("0"),
        widget=forms.NumberInput(
            attrs={
                "min": "0",
                "step": "0.01",
                "inputmode": "decimal",
                "class": "expense-share-input",
                "data-share-username": "yeye",
            }
        ),
    )

    nainai_amount = forms.DecimalField(
        label="ばあばの負担額",
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        initial=Decimal("0"),
        widget=forms.NumberInput(
            attrs={
                "min": "0",
                "step": "0.01",
                "inputmode": "decimal",
                "class": "expense-share-input",
                "data-share-username": "nainai",
            }
        ),
    )

    class Meta:
        model = Expense

        fields = (
            "title",
            "total_amount",
            "currency",
            "paid_by",
            "paid_at",
            "category",
            "note",
        )

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "例：昼食、タクシー、おむつ",
                }
            ),
            "total_amount": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                    "inputmode": "decimal",
                    "data-expense-total": "true",
                }
            ),
            "paid_at": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "data-default-now": "true",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "note": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "必要な場合だけ入力",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        User = get_user_model()

        self.fields["paid_by"].queryset = User.objects.filter(
            is_active=True,
            is_superuser=False,
        ).order_by(
            "username",
        )

        self.fields["paid_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        if self.instance and self.instance.pk:
            shares_by_username = {
                share.user.username: share.amount
                for share in self.instance.shares.select_related(
                    "user",
                ).all()
            }

            field_mapping = {
                "papa": "papa_amount",
                "mama": "mama_amount",
                "yeye": "yeye_amount",
                "nainai": "nainai_amount",
            }

            for username, field_name in field_mapping.items():
                self.fields[field_name].initial = (
                    shares_by_username.get(
                        username,
                        Decimal("0"),
                    )
                )

    def clean(self):
        cleaned_data = super().clean()

        total_amount = cleaned_data.get("total_amount")

        share_field_names = (
            "papa_amount",
            "mama_amount",
            "yeye_amount",
            "nainai_amount",
        )

        share_total = Decimal("0")

        for field_name in share_field_names:
            amount = cleaned_data.get(field_name)

            if amount is None:
                amount = Decimal("0")
                cleaned_data[field_name] = amount

            share_total += amount

        if (
            total_amount is not None
            and share_total != total_amount
        ):
            difference = total_amount - share_total

            if difference > 0:
                message = (
                    "負担額の合計が、支出総額より"
                    f"{difference}少ない。"
                )
            else:
                message = (
                    "負担額の合計が、支出総額を"
                    f"{abs(difference)}超えている。"
                )

            raise forms.ValidationError(
                message
            )

        return cleaned_data

class BabyGrowthNoteForm(forms.ModelForm):
    class Meta:
        model = BabyGrowthNote

        fields = (
            "observed_on",
            "content",
        )

        widgets = {
            "observed_on": forms.DateInput(
                attrs={
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            "content": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "例：今日は初めて「ばばば」と長くおしゃべりした。"
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["observed_on"].input_formats = [
            "%Y-%m-%d",
        ]