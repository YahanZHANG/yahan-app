from .i18n import t
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import (
    Child,
    ChildCollaborator,
    Country,
    HealthcareProvider,
    VaccinationRecord,
    VaccinationSettings,
    VaccinePreparation,
    VaccineProduct,
)


REACTION_CHOICES = [
    ("fever", "発熱"),
    ("swelling", "接種部位の腫れ"),
    ("redness", "発赤"),
    ("pain", "痛み"),
    ("rash", "発疹"),
    ("vomiting", "嘔吐"),
    ("diarrhea", "下痢"),
    ("sleepiness", "眠気"),
    ("irritability", "不機嫌"),
]


class LocalizedPreparationChoiceField(
    forms.ModelChoiceField
):
    def __init__(
        self,
        *args,
        language_code="ja",
        **kwargs,
    ):
        self.language_code = language_code
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return obj.get_name(
            self.language_code
        )


class LocalizedCountryChoiceField(
    forms.ModelChoiceField
):
    def __init__(
        self,
        *args,
        language_code="ja",
        **kwargs,
    ):
        self.language_code = language_code
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return obj.get_name(
            self.language_code
        )

class VaccineProductChoiceField(
    forms.ModelChoiceField
):
    def label_from_instance(
        self,
        obj,
    ):
        if obj.manufacturer:
            return (
                f"{obj.product_name} "
                f"— {obj.manufacturer}"
            )

        return obj.product_name

class ChildForm(forms.ModelForm):
    class Meta:
        model = Child

        fields = [
            "name",
            "name_en",
            "date_of_birth",
            "birth_country",
            "default_country",
        ]

        labels = {
            "name": "名前",
            "date_of_birth": "生年月日",
            "birth_country": "出生国",
            "default_country": "現在住んでいる国",
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "vaccination-input",
                    "placeholder": "例：のいちゃん",
                    "autocomplete": "off",
                }
            ),

            "date_of_birth": forms.DateInput(
                attrs={
                    "class": "vaccination-input",
                    "type": "date",
                }
            ),

            "birth_country": forms.Select(
                attrs={
                    "class": "vaccination-input",
                }
            ),

            "default_country": forms.Select(
                attrs={
                    "class": "vaccination-input",
                }
            ),
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.fields["name_en"].required = True
            self.fields["name_en"].label = "English name"

class VaccinationRecordForm(forms.ModelForm):

    preparation = LocalizedPreparationChoiceField(
        queryset=VaccinePreparation.objects.none(),
        label="ワクチン",
        empty_label="ワクチンを選択",
    )

    country = LocalizedCountryChoiceField(
        queryset=Country.objects.none(),
        label="接種した国",
        empty_label="国を選択",
        required=False,
    )

    product = VaccineProductChoiceField(
        queryset=VaccineProduct.objects.none(),
        required=False,
        empty_label="製品を選択",
        widget=forms.Select(
            attrs={
                "class": "vaccination-input",
            }
        ),
    )

    healthcare_provider = forms.ModelChoiceField(
        queryset=HealthcareProvider.objects.none(),
        label="医療機関",
        required=False,
        empty_label=None,
        widget=forms.RadioSelect,
    )

    new_provider_name = forms.CharField(
        label="新しい医療機関",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "vaccination-input",
                "placeholder": "病院・小児科・クリニック名",
                "autocomplete": "off",
            }
        ),
    )

    new_provider_city = forms.CharField(
        label="市・地域",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "vaccination-input",
                "placeholder": "例：Zürich",
                "autocomplete": "off",
            }
        ),
    )

    reactions = forms.MultipleChoiceField(
        label="副反応",
        choices=REACTION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = VaccinationRecord

        fields = [
            "preparation",
            "vaccination_date",
            "country",
            "healthcare_provider",
            "preparation_dose_number",

            "product",
            "product_name",
            "manufacturer",
            "lot_number",

            "no_reaction",
            "reaction_other",
            "notes",
        ]

        labels = {
            "vaccination_date": "接種日",
            "preparation_dose_number": "この製剤として何回目",
            "product_name": "商品名",
            "manufacturer": "メーカー",
            "lot_number": "Lot番号",
            "no_reaction": "副反応なし",
            "reaction_other": "その他の副反応",
            "notes": "メモ",
        }

        widgets = {
            "vaccination_date": forms.DateInput(
                attrs={
                    "class": "vaccination-input",
                    "type": "date",
                }
            ),

            "preparation_dose_number": forms.NumberInput(
                attrs={
                    "class": "vaccination-input",
                    "min": "1",
                    "placeholder": "例：2",
                }
            ),

            "product_name": forms.TextInput(
                attrs={
                    "class": "vaccination-input",
                    "placeholder": "例：Priorix",
                }
            ),

            "manufacturer": forms.TextInput(
                attrs={
                    "class": "vaccination-input",
                    "placeholder": "例：GSK",
                }
            ),

            "lot_number": forms.TextInput(
                attrs={
                    "class": "vaccination-input",
                    "placeholder": "例：AB1234",
                }
            ),

            "no_reaction": forms.CheckboxInput(),

            "reaction_other": forms.TextInput(
                attrs={
                    "class": "vaccination-input",
                    "placeholder": "その他",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "vaccination-input",
                    "rows": 4,
                    "placeholder": "必要ならメモを追加",
                }
            ),
        }

    def __init__(
        self,
        *args,
        user=None,
        language_code="ja",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.fields["preparation"] = (
            LocalizedPreparationChoiceField(
                queryset=(
                    VaccinePreparation.objects
                    .prefetch_related(
                        "translations",
                        "components",
                    )
                    .order_by("name_en")
                ),
                language_code=language_code,
                label="ワクチン",
                empty_label="ワクチンを選択",
                widget=forms.Select(
                    attrs={
                        "class": "vaccination-input",
                    }
                ),
            )
        )

        self.fields["country"] = (
            LocalizedCountryChoiceField(
                queryset=(
                    Country.objects
                    .prefetch_related(
                        "translations"
                    )
                    .order_by("name_en")
                ),
                language_code=language_code,
                label="接種した国",
                empty_label="国を選択",
                required=False,
                widget=forms.Select(
                    attrs={
                        "class": "vaccination-input",
                    }
                ),
            )
        )

        if user:
            providers = (
                HealthcareProvider.objects
                .filter(owner=user)
                .order_by(
                    "-last_used_at",
                    "-id",
                )
            )

            self.fields[
                "healthcare_provider"
            ].queryset = providers

        else:
            self.fields[
                "healthcare_provider"
            ].queryset = (
                HealthcareProvider.objects.none()
            )

        if self.instance.pk:
            self.fields[
                "reactions"
            ].initial = (
                self.instance.reaction_codes
            )

        self.fields["preparation"].label = t(
            "vaccine",
            language_code,
        )

        self.fields["preparation"].empty_label = t(
            "select_vaccine",
            language_code,
        )

        self.fields["vaccination_date"].label = t(
            "vaccination_date",
            language_code,
        )

        self.fields["country"].label = t(
            "vaccination_country",
            language_code,
        )

        self.fields["country"].empty_label = t(
            "select_country",
            language_code,
        )

        self.fields["healthcare_provider"].label = t(
            "healthcare_provider",
            language_code,
        )

        self.fields["new_provider_name"].label = t(
            "new_provider",
            language_code,
        )

        self.fields["new_provider_city"].label = t(
            "city_region",
            language_code,
        )

        self.fields[
            "preparation_dose_number"
        ].label = t(
            "preparation_dose",
            language_code,
        )

        self.fields["product_name"].label = t(
            "product_name",
            language_code,
        )

        self.fields["manufacturer"].label = t(
            "manufacturer",
            language_code,
        )

        self.fields["lot_number"].label = t(
            "lot_number",
            language_code,
        )

        self.fields["reaction_other"].label = t(
            "other_reaction",
            language_code,
        )

        self.fields["notes"].label = t(
            "notes",
            language_code,
        )

        self.fields[
            "new_provider_name"
        ].widget.attrs["placeholder"] = t(
            "provider_placeholder",
            language_code,
        )

        self.fields[
            "new_provider_city"
        ].widget.attrs["placeholder"] = t(
            "city_placeholder",
            language_code,
        )

        self.fields["reactions"].choices = [
            (
                "fever",
                t("reaction_fever", language_code),
            ),
            (
                "swelling",
                t("reaction_swelling", language_code),
            ),
            (
                "redness",
                t("reaction_redness", language_code),
            ),
            (
                "pain",
                t("reaction_pain", language_code),
            ),
            (
                "rash",
                t("reaction_rash", language_code),
            ),
            (
                "vomiting",
                t("reaction_vomiting", language_code),
            ),
            (
                "diarrhea",
                t("reaction_diarrhea", language_code),
            ),
            (
                "sleepiness",
                t("reaction_sleepiness", language_code),
            ),
            (
                "irritability",
                t(
                    "reaction_irritability",
                    language_code,
                ),
            ),
        ]

        self.fields["product"].queryset = (
            VaccineProduct.objects
            .select_related(
                "preparation"
            )
            .order_by(
                "product_name"
            )
        )

        self.fields["product"].label = (
            "登録済み製品"
        )

    def clean(self):
        cleaned_data = super().clean()

        # --------------------------------------------------
        # Reactions
        # --------------------------------------------------

        if cleaned_data.get(
            "no_reaction"
        ):
            cleaned_data[
                "reactions"
            ] = []

            cleaned_data[
                "reaction_other"
            ] = ""

        # --------------------------------------------------
        # Vaccine product
        # --------------------------------------------------

        product = cleaned_data.get(
            "product"
        )

        preparation = cleaned_data.get(
            "preparation"
        )

        if product:

            # 選択した製品とワクチン製剤が一致するか確認
            if (
                preparation
                and
                product.preparation_id
                != preparation.id
            ):
                self.add_error(
                    "product",
                    (
                        "選択したワクチンと"
                        "製品が一致していません。"
                    ),
                )

            else:

                # 製品を選んだ場合、
                # 商品名・メーカーを自動保存
                cleaned_data[
                    "product_name"
                ] = product.product_name

                cleaned_data[
                    "manufacturer"
                ] = (
                    product.manufacturer
                )

        return cleaned_data

class VaccinationSettingsForm(forms.ModelForm):

    ui_language = forms.ChoiceField(
        label="アプリの言語",
        choices=settings.LANGUAGES,
        widget=forms.Select(
            attrs={
                "class": "vaccination-input",
            }
        ),
    )

    current_country = LocalizedCountryChoiceField(
        queryset=Country.objects.none(),
        label="現在住んでいる国",
        required=False,
        empty_label="国を選択",
    )

    doctor_language = forms.ChoiceField(
        label="Doctor Modeの言語",
        choices=settings.LANGUAGES,
        widget=forms.Select(
            attrs={
                "class": "vaccination-input",
            }
        ),
    )

    class Meta:
        model = VaccinationSettings

        fields = [
            "ui_language",
            "current_country",
            "doctor_language",
            "doctor_show_english",
            "date_format",
        ]

        labels = {
            "doctor_show_english": "英語を併記する",
            "date_format": "日付形式",
        }

        widgets = {
            "doctor_show_english": forms.CheckboxInput(),

            "date_format": forms.Select(
                attrs={
                    "class": "vaccination-input",
                }
            ),
        }

    def __init__(
        self,
        *args,
        language_code="ja",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.fields["current_country"] = (
            LocalizedCountryChoiceField(
                queryset=(
                    Country.objects
                    .prefetch_related(
                        "translations"
                    )
                    .order_by("name_en")
                ),
                language_code=language_code,
                label="現在住んでいる国",
                required=False,
                empty_label="国を選択",
                widget=forms.Select(
                    attrs={
                        "class": "vaccination-input",
                    }
                ),
            )
        )

        self.fields["ui_language"].label = t(
            "app_language",
            language_code,
        )

        self.fields["current_country"].label = t(
            "current_country",
            language_code,
        )

        self.fields["doctor_language"].label = t(
            "doctor_language",
            language_code,
        )

        self.fields[
            "doctor_show_english"
        ].label = t(
            "show_english",
            language_code,
        )

        self.fields["date_format"].label = t(
            "date_format",
            language_code,
        )


class CollaboratorForm(forms.Form):

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "vaccination-input",
                "placeholder": "username",
                "autocomplete": "off",
            }
        ),
    )

    permission = forms.ChoiceField(
        choices=[],
        widget=forms.Select(
            attrs={
                "class": "vaccination-input",
            }
        ),
    )

    def __init__(
        self,
        *args,
        child=None,
        language_code="ja",
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.child = child

        self.fields[
            "permission"
        ].choices = [
            (
                ChildCollaborator
                .PERMISSION_EDIT,
                t(
                    "permission_edit",
                    language_code,
                ),
            ),
            (
                ChildCollaborator
                .PERMISSION_VIEW,
                t(
                    "permission_view",
                    language_code,
                ),
            ),
        ]

    def clean_username(self):

        username = (
            self.cleaned_data[
                "username"
            ]
            .strip()
        )

        User = get_user_model()

        user = (
            User.objects
            .filter(
                username=username
            )
            .first()
        )

        if user is None:
            raise forms.ValidationError(
                "ユーザーが見つかりません。"
            )

        if (
            self.child
            and
            self.child.owner_id
            == user.id
        ):
            raise forms.ValidationError(
                "このユーザーは所有者です。"
            )

        self.collaborator_user = user

        return username