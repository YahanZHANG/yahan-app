from django import forms

from .models import (
    SwissBoardPost,
    SwissBoardProfile,
    SwissBoardComment,
)


# =========================================================
# Swiss Board Post Form
# =========================================================

class SwissBoardPostForm(forms.ModelForm):

    subcategory = forms.ChoiceField(
        label="サブカテゴリー",
        required=False,
        choices=[("", "先にカテゴリーを選択")],
        widget=forms.Select(
            attrs={"id": "sb-subcategory"}
        ),
    )

    REGION_CHOICES = [
        ("", "指定しない"),
        ("Zürich", "Zürich"),
        ("Winterthur", "Winterthur"),
        ("Basel", "Basel"),
        ("Bern", "Bern"),
        ("Luzern", "Luzern"),
        ("Zug", "Zug"),
        ("Baden", "Baden"),
        ("Aarau", "Aarau"),
        ("St. Gallen", "St. Gallen"),
        ("Schaffhausen", "Schaffhausen"),
        ("Chur", "Chur"),
        ("Lausanne", "Lausanne"),
        ("Genève", "Genève"),
        ("Neuchâtel", "Neuchâtel"),
        ("Fribourg", "Fribourg"),
        ("Biel/Bienne", "Biel/Bienne"),
        ("Lugano", "Lugano"),
        ("other", "その他（自由入力）"),
    ]

    region_choice = forms.ChoiceField(
        label="地域",
        choices=REGION_CHOICES,
        required=False,
        widget=forms.Select(
            attrs={"id": "sb-region-choice"}
        ),
    )

    region_other = forms.CharField(
        label="その他の地域",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "id": "sb-region-other",
                "placeholder": "例：Oberengstringen",
                "maxlength": 100,
            }
        ),
    )

    class Meta:

        model = SwissBoardPost

        fields = [
            "title",
            "body",
            "category",
            "subcategory",
            "region",
        ]

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "placeholder": "投稿タイトル（30文字以内）",
                    "maxlength": 30,
                }
            ),

            "body": forms.Textarea(
                attrs={
                    "placeholder": "投稿内容を入力してください",
                    "rows": 8,
                    "maxlength": 500,
                }
            ),

            "category": forms.Select(
                attrs={"id": "sb-category"}
            ),

            "region": forms.HiddenInput(),

        }

    def __init__(
        self,
        *args,
        category_map=None,
        **kwargs
    ):

        super().__init__(*args, **kwargs)

        self.category_map = category_map or {}

        self.fields["category"].empty_label = (
            "カテゴリーを選択"
        )

        if self.is_bound:

            category = self.data.get(
                "category", ""
            )

        else:

            category = self.initial.get(
                "category", ""
            )

        subcategories = self.category_map.get(
            category,
            [],
        )

        self.fields["subcategory"].choices = [
            ("", "サブカテゴリーを選択（任意）"),
            *[
                (name, name)
                for name in subcategories
            ],
        ]

    def clean_subcategory(self):

        subcategory = self.cleaned_data.get(
            "subcategory", ""
        )

        category = self.data.get(
            "category", ""
        ) if self.is_bound else self.initial.get(
            "category", ""
        )

        if subcategory and subcategory not in (
            self.category_map.get(category, [])
        ):
            raise forms.ValidationError(
                "選択したカテゴリーに対応する"
                "サブカテゴリーを選んでください。"
            )

        return subcategory

    def clean(self):
        cleaned_data = super().clean()

        choice = cleaned_data.get("region_choice", "")
        other = cleaned_data.get("region_other", "").strip()

        if choice == "other":

            if not other:
                self.add_error(
                    "region_other",
                    "地域名を入力してください。",
                )
                region = ""
            else:
                region = other

        else:
            region = choice

        # Always determine the stored region server-side.
        cleaned_data["region"] = region

        return cleaned_data


# =========================================================
# Swiss Board Profile Form
# =========================================================

class SwissBoardProfileForm(forms.ModelForm):

    class Meta:

        model = SwissBoardProfile

        fields = [
            "display_name",
        ]

        widgets = {
            "display_name": forms.TextInput(
                attrs={
                    "placeholder": "例：スイス生活ママ",
                    "maxlength": 30,
                    "autocomplete": "nickname",
                }
            ),
        }

    def clean_display_name(self):

        display_name = (
            self.cleaned_data.get("display_name") or ""
        ).strip()

        if len(display_name) < 2:
            raise forms.ValidationError(
                "表示名は2文字以上で入力してください。"
            )

        return display_name


# =========================================================
# Swiss Board Comment Form
# =========================================================

class SwissBoardCommentForm(forms.ModelForm):

    class Meta:
        model = SwissBoardComment
        fields = ["body"]

        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 500,
                    "placeholder": "コメントを入力してください（500文字以内）",
                }
            ),
        }

    def clean_body(self):
        body = (
            self.cleaned_data.get("body") or ""
        ).strip()

        if not body:
            raise forms.ValidationError(
                "コメントを入力してください。"
            )

        return body