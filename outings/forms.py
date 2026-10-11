
from django import forms
from django.utils import timezone

from .models import Event, EventCategory


CANTON_CHOICES = [
    ("", "州を選択"),
    ("ZH", "Zürich"),
    ("BS", "Basel-Stadt"),
    ("BL", "Basel-Landschaft"),
    ("ZG", "Zug"),
    ("LU", "Luzern"),
    ("AG", "Aargau"),
    ("SZ", "Schwyz"),
    ("SO", "Solothurn"),
    ("NW", "Nidwalden"),
    ("OW", "Obwalden"),
]


class EventSubmissionForm(forms.ModelForm):

    venue_name = forms.CharField(
        label="会場名",
        max_length=200,
    )

    city = forms.CharField(
        label="都市・市町村",
        max_length=120,
    )

    canton = forms.ChoiceField(
        label="州",
        choices=CANTON_CHOICES,
    )

    address = forms.CharField(
        label="住所",
        max_length=300,
        required=False,
    )

    start_at = forms.DateTimeField(
        label="開始日時",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    end_at = forms.DateTimeField(
        label="終了日時",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )


    price_type = forms.ChoiceField(
        label="料金",
        choices=[
            ("free", "無料"),
            ("paid", "有料"),
        ],
        widget=forms.RadioSelect,
        initial="free",
    )

    venue_type = forms.ChoiceField(
        label="開催場所",
        choices=[
            ("indoor", "屋内"),
            ("outdoor", "屋外"),
            ("both", "屋内・屋外の両方"),
        ],
        widget=forms.RadioSelect,
        initial="indoor",
    )



    class Meta:
        model = Event

        fields = [
            "title",
            "summary_ja",
            "category",
            "event_type",
            "language_barrier",
            "price_text",
            "original_url",
        ]

        labels = {
            "title": "イベント名",
            "summary_ja": "イベントの説明",
            "category": "カテゴリー",
            "event_type": "開催形態",
            "language_barrier": "参加に必要な言語",
            "is_free": "無料イベント",
            "price_text": "料金",
            "is_indoor": "屋内",
            "is_outdoor": "屋外",
            "original_url": "イベントの公式URL",
        }

        widgets = {
            "summary_ja": forms.Textarea(
                attrs={"rows": 6}
            ),
            "price_text": forms.TextInput(
                attrs={"placeholder": "例：大人 CHF 10"}
            ),
            "original_url": forms.URLInput(
                attrs={"placeholder": "https://"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = (
            EventCategory.objects.filter(
                is_active=True
            ).order_by("sort_order", "name")
        )

        self.fields["category"].required = True
        self.fields["category"].empty_label = (
            "カテゴリーを選択"
        )

        self.fields["title"].required = True
        self.fields["summary_ja"].required = True

        self.fields["language_barrier"].required = True

        self.fields["price_text"].required = False

        self.order_fields([
            "title",
            "summary_ja",
            "category",
            "event_type",
            "start_at",
            "end_at",
            "venue_name",
            "city",
            "canton",
            "address",
            "language_barrier",
            "price_type",
            "price_text",
            "venue_type",
            "original_url",
        ])

    def clean(self):
        cleaned_data = super().clean()

        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if start_at and end_at:
            if end_at <= start_at:
                self.add_error(
                    "end_at",
                    "終了日時は開始日時より後に設定して。",
                )

        if end_at and end_at <= timezone.now():
            self.add_error(
                "end_at",
                "終了日時が過去のイベントは投稿できない。",
            )


        if cleaned_data.get("price_type") == "free":
            cleaned_data["price_text"] = ""

        elif not cleaned_data.get("price_text", "").strip():
            self.add_error(
                "price_text",
                "有料の場合は料金を入力して。",
            )


        return cleaned_data

    
    def save(self, commit=True):
        event = super().save(commit=False)

        event.is_free = (
            self.cleaned_data["price_type"] == "free"
        )

        venue_type = self.cleaned_data["venue_type"]

        event.is_indoor = venue_type in ("indoor", "both")
        event.is_outdoor = venue_type in ("outdoor", "both")

        if commit:
            event.save()
            self.save_m2m()

        return event

