from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
    Allergen,
    AllergyReaction,
    Baby,
    BabyMembership,
    CommercialBrand,
    Dish,
    DishCategory,
    DishIngredient,
    FeedingGroup,
    Food,
    FoodCategory,
    Meal,
    MealItem,
    Supplement,
)


class FoodChoiceField(forms.ModelChoiceField):
    """食材名とジャンルを選択肢に表示する。"""

    def label_from_instance(self, obj):
        return f"{obj.category.name}｜{obj.name}"


class DishChoiceField(forms.ModelChoiceField):
    """料理名と料理ジャンルを選択肢に表示する。"""

    def label_from_instance(self, obj):
        return f"{obj.category.name}｜{obj.name}"


class CategoryDataSelect(forms.Select):
    """
    各optionにジャンルIDを埋め込むSelect。
    JavaScriptでジャンル別に選択肢を絞り込むために使う。
    """

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )

        instance = getattr(
            value,
            "instance",
            None,
        )

        if instance is not None:
            option["attrs"]["data-category-id"] = str(
                instance.category_id
            )

        return option

class CommercialProductSelect(forms.Select):
    """
    各市販品optionにメーカーIDを埋め込むSelect。
    JavaScriptでメーカー別に候補を絞り込むために使う。
    """

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )

        instance = getattr(
            value,
            "instance",
            None,
        )

        if (
            instance is not None
            and instance.commercial_brand_id
        ):
            option["attrs"]["data-brand"] = str(
                instance.commercial_brand_id
            )

        return option

class MealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = ("date",)
        widgets = {
            "date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                },
            ),
        }
        labels = {
            "date": "日付",
        }


class MealItemForm(forms.ModelForm):
    item_type = forms.ChoiceField(
        choices=MealItem.ItemType.choices,
        initial=MealItem.ItemType.FOOD,
        widget=forms.HiddenInput(
            attrs={
                "class": "item-type-select",
            }
        ),
    )

    catalog_type = forms.ChoiceField(
        required=False,
        choices=[
            ("food", "食材"),
            ("dish", "料理"),
            ("commercial", "市販品"),
        ],
        initial="food",
        widget=forms.HiddenInput(
            attrs={
                "class": "catalog-type-select",
            }
        ),
    )

    food_category = forms.ModelChoiceField(
        label="食材ジャンル",
        queryset=FoodCategory.objects.none(),
        required=False,
        empty_label="食材ジャンルを選択",
        widget=forms.Select(
            attrs={
                "class": (
                    "form-control "
                    "food-category-select"
                ),
            }
        ),
    )

    dish_category = forms.ModelChoiceField(
        label="料理ジャンル",
        queryset=DishCategory.objects.none(),
        required=False,
        empty_label="料理ジャンルを選択",
        widget=forms.Select(
            attrs={
                "class": (
                    "form-control "
                    "dish-category-select"
                ),
            }
        ),
    )

    food = FoodChoiceField(
        label="食材名",
        queryset=Food.objects.none(),
        required=False,
        empty_label="食材を選択",
        widget=CategoryDataSelect(
            attrs={
                "class": (
                    "form-control "
                    "food-select"
                ),
            }
        ),
    )

    dish = DishChoiceField(
        label="料理名",
        queryset=Dish.objects.none(),
        required=False,
        empty_label="料理を選択",
        widget=CategoryDataSelect(
            attrs={
                "class": (
                    "form-control "
                    "dish-select"
                ),
            }
        ),
    )

    commercial_brand = forms.ModelChoiceField(
        label="メーカー",
        required=False,
        queryset=CommercialBrand.objects.none(),
        empty_label="メーカーを選択",
        widget=forms.Select(
            attrs={
                "class": (
                    "form-control "
                    "commercial-brand-select"
                ),
            }
        ),
    )

    commercial_product = forms.ModelChoiceField(
        label="市販品名",
        required=False,
        queryset=Dish.objects.none(),
        empty_label="先にメーカーを選択",
        widget=CommercialProductSelect(
            attrs={
                "class": (
                    "form-control "
                    "commercial-product-select"
                ),
            }
        ),
    )

    unit = forms.ChoiceField(
        choices=[
            (
                MealItem.Unit.GRAM,
                "g",
            ),
        ],
        initial=MealItem.Unit.GRAM,
        required=False,
        widget=forms.HiddenInput(
            attrs={
                "class": "meal-unit-input",
            }
        ),
    )

    reaction = forms.ChoiceField(
        label="反応",
        required=False,
        choices=[
            ("", "未選択"),
            ("love", "🤩"),
            ("happy", "😊"),
            ("normal", "😐"),
            ("unsure", "😕"),
        ],
        widget=forms.RadioSelect(
            attrs={
                "class": (
                    "reaction-radio-input"
                ),
            }
        ),
    )

    class Meta:
        model = MealItem
        fields = (
            "item_type",
            "food_category",
            "food",
            "dish_category",
            "dish",
            "amount",
            "unit",
            "reaction",
            "has_allergy_symptoms",
        )
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0.01",
                    "step": "0.01",
                    "inputmode": "decimal",
                    "placeholder": "例：30",
                },
            ),
            "has_allergy_symptoms": forms.CheckboxInput(
                attrs={
                    "class": (
                        "allergy-symptom-checkbox"
                    ),
                }
            ),
        }
        labels = {
            "amount": "実際に食べた量(g)",
            "has_allergy_symptoms": "症状が出た",
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.fields[
            "commercial_brand"
        ].queryset = (
            CommercialBrand.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "display_order",
                "name",
            )
        )

        instance = self.instance

        self.fields["food_category"].queryset = (
            FoodCategory.objects
            .filter(is_active=True)
            .order_by(
                "display_order",
                "name",
            )
        )

        self.fields["dish_category"].queryset = (
            DishCategory.objects
            .filter(is_active=True)
            .order_by(
                "display_order",
                "name",
            )
        )

        self.fields["unit"].initial = (
            MealItem.Unit.GRAM
        )

        if instance and instance.pk:
            self.fields["item_type"].initial = (
                instance.item_type
            )
        else:
            self.fields["item_type"].initial = (
                MealItem.ItemType.FOOD
            )

        food_query = Food.objects.filter(
            is_active=True,
        )

        if (
            instance
            and instance.pk
            and instance.food_id
        ):
            food_query = Food.objects.filter(
                Q(is_active=True)
                | Q(pk=instance.food_id)
            )

            self.fields["food_category"].initial = (
                instance.food.category_id
            )

        self.fields["food"].queryset = (
            food_query
            .select_related("category")
            .order_by(
                "category__display_order",
                "category__name",
                "name",
            )
        )

        dish_query = Dish.objects.filter(
            is_active=True,
            is_commercial_product=False,
        )

        if (
            instance
            and instance.pk
            and instance.dish_id
            and not instance.dish.is_commercial_product
        ):
            dish_query = Dish.objects.filter(
                Q(
                    is_active=True,
                    is_commercial_product=False,
                )
                | Q(pk=instance.dish_id)
            )

            self.fields["dish_category"].initial = (
                instance.dish.category_id
            )

        self.fields["dish"].queryset = (
            dish_query
            .select_related("category")
            .order_by(
                "category__display_order",
                "category__name",
                "name",
            )
        )

        commercial_query = Dish.objects.filter(
            is_active=True,
            is_commercial_product=True,
        )

        if (
            instance
            and instance.pk
            and instance.dish_id
            and instance.dish.is_commercial_product
        ):
            commercial_query = Dish.objects.filter(
                Q(
                    is_active=True,
                    is_commercial_product=True,
                )
                | Q(pk=instance.dish_id)
            )

        self.fields["commercial_product"].queryset = (
            commercial_query
            .select_related(
                "commercial_brand",
            )
            .order_by(
                "commercial_brand__display_order",
                "commercial_brand__name",
                "recommended_from_month",
                "name",
            )
        )

        if (
            instance
            and instance.pk
            and instance.dish_id
            and instance.dish.is_commercial_product
        ):
            self.fields["catalog_type"].initial = (
                "commercial"
            )
            self.fields["commercial_brand"].initial = (
                instance.dish.commercial_brand_id
            )
            self.fields["commercial_product"].initial = (
                instance.dish
            )

        elif (
            instance
            and instance.pk
            and instance.item_type
            == MealItem.ItemType.DISH
        ):
            self.fields["catalog_type"].initial = "dish"

        else:
            self.fields["catalog_type"].initial = "food"

    def clean_unit(self):
        return MealItem.Unit.GRAM

    def clean(self):
        cleaned_data = super().clean()

        # ----------------------------------------
        # 完全に未入力の行は、そのまま無視する
        # ----------------------------------------
        row_has_input = any(
            [
                cleaned_data.get("food_category"),
                cleaned_data.get("food"),
                cleaned_data.get("dish_category"),
                cleaned_data.get("dish"),
                cleaned_data.get("commercial_brand"),
                cleaned_data.get("commercial_product"),
                cleaned_data.get("amount"),
                cleaned_data.get("reaction"),
                cleaned_data.get("has_allergy_symptoms"),
            ]
        )

        if not row_has_input:
            return cleaned_data

        catalog_type = (
            cleaned_data.get("catalog_type")
            or "food"
        )
        food_category = cleaned_data.get(
            "food_category"
        )
        food = cleaned_data.get("food")
        dish_category = cleaned_data.get(
            "dish_category"
        )
        dish = cleaned_data.get("dish")
        commercial_brand = cleaned_data.get(
            "commercial_brand"
        )
        commercial_product = cleaned_data.get(
            "commercial_product"
        )

        cleaned_data["unit"] = (
            MealItem.Unit.GRAM
        )

        if catalog_type == "food":
            cleaned_data["item_type"] = (
                MealItem.ItemType.FOOD
            )

            if food_category is None:
                self.add_error(
                    "food_category",
                    "食材ジャンルを選択してください。",
                )

            if food is None:
                self.add_error(
                    "food",
                    "食材を選択してください。",
                )

            if (
                food
                and food_category
                and food.category_id
                != food_category.id
            ):
                self.add_error(
                    "food",
                    (
                        "選択したジャンルに属する"
                        "食材を選んでください。"
                    ),
                )

            cleaned_data["dish"] = None
            cleaned_data["dish_category"] = None
            cleaned_data["commercial_brand"] = None
            cleaned_data["commercial_product"] = None

        elif catalog_type == "dish":
            cleaned_data["item_type"] = (
                MealItem.ItemType.DISH
            )

            if dish_category is None:
                self.add_error(
                    "dish_category",
                    "料理ジャンルを選択してください。",
                )

            if dish is None:
                self.add_error(
                    "dish",
                    "料理を選択してください。",
                )

            if (
                dish
                and dish.is_commercial_product
            ):
                self.add_error(
                    "dish",
                    (
                        "市販品は市販品タブから"
                        "選択してください。"
                    ),
                )

            if (
                dish
                and dish_category
                and dish.category_id
                != dish_category.id
            ):
                self.add_error(
                    "dish",
                    (
                        "選択したジャンルに属する"
                        "料理を選んでください。"
                    ),
                )

            cleaned_data["food"] = None
            cleaned_data["food_category"] = None
            cleaned_data["commercial_brand"] = None
            cleaned_data["commercial_product"] = None

        elif catalog_type == "commercial":
            cleaned_data["item_type"] = (
                MealItem.ItemType.DISH
            )

            if not commercial_brand:
                self.add_error(
                    "commercial_brand",
                    "メーカーを選択してください。",
                )

            if commercial_product is None:
                self.add_error(
                    "commercial_product",
                    "市販品を選択してください。",
                )

            if (
                commercial_product
                and not (
                    commercial_product
                    .is_commercial_product
                )
            ):
                self.add_error(
                    "commercial_product",
                    (
                        "市販品として登録された"
                        "商品を選択してください。"
                    ),
                )

            if (
                commercial_product
                and commercial_brand
                and (
                    commercial_product
                    .commercial_brand_id
                    != commercial_brand.id
                )
            ):
                self.add_error(
                    "commercial_product",
                    (
                        "選択したメーカーの商品を"
                        "選んでください。"
                    ),
                )

            cleaned_data["dish"] = commercial_product
            cleaned_data["food"] = None
            cleaned_data["food_category"] = None
            cleaned_data["dish_category"] = None

        else:
            self.add_error(
                "catalog_type",
                "入力形式が正しくありません。",
            )

        return cleaned_data


class BaseMealItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(
            form.errors
            for form in self.forms
        ):
            return

        active_item_count = 0
        selected_items = set()

        for form in self.forms:
            cleaned_data = getattr(
                form,
                "cleaned_data",
                {},
            )

            if not cleaned_data:
                continue

            if cleaned_data.get("DELETE"):
                continue

            item_type = cleaned_data.get(
                "item_type"
            )

            if not item_type:
                continue

            food = cleaned_data.get("food")
            dish = cleaned_data.get("dish")

            if (
                item_type
                == MealItem.ItemType.FOOD
                and food
            ):
                selected_key = (
                    "food",
                    food.pk,
                )
                selected_field = "food"
                active_item_count += 1

            elif (
                item_type
                == MealItem.ItemType.DISH
                and dish
            ):
                selected_key = (
                    "dish",
                    dish.pk,
                )

                catalog_type = (
                    cleaned_data.get(
                        "catalog_type"
                    )
                )

                if catalog_type == "commercial":
                    selected_field = (
                        "commercial_product"
                    )
                else:
                    selected_field = "dish"

                active_item_count += 1

            else:
                continue

            if selected_key in selected_items:
                form.add_error(
                    selected_field,
                    (
                        "同じ食材・料理・市販品が"
                        "この食事内ですでに"
                        "選択されている。"
                    ),
                )
            else:
                selected_items.add(
                    selected_key
                )


MealItemCreateFormSet = inlineformset_factory(
    Meal,
    MealItem,
    form=MealItemForm,
    formset=BaseMealItemFormSet,
    extra=3,
    can_delete=True,
    max_num=30,
    validate_max=True,
)

MealItemEditFormSet = inlineformset_factory(
    Meal,
    MealItem,
    form=MealItemForm,
    formset=BaseMealItemFormSet,
    extra=1,
    can_delete=True,
    max_num=30,
    validate_max=True,
)


SYMPTOM_CHOICES = [
    ("mouth_redness", "口の周りの赤み"),
    ("face_redness", "顔の赤み"),
    ("rash", "発疹"),
    ("hives", "じんましん"),
    ("itching", "かゆみ"),
    ("eyelid_swelling", "まぶたの腫れ"),
    ("lip_swelling", "唇の腫れ"),
    ("vomiting", "嘔吐"),
    ("diarrhea", "下痢"),
    ("cough", "咳"),
    ("wheezing", "ゼーゼー"),
    ("breathing_difficulty", "呼吸が苦しそう"),
    ("low_energy", "元気がない"),
    ("altered_consciousness", "意識状態がおかしい"),
    ("other", "その他"),
]


BODY_LOCATION_CHOICES = [
    ("mouth", "口の周り"),
    ("face", "顔"),
    ("neck", "首"),
    ("chest", "胸"),
    ("abdomen", "お腹"),
    ("back", "背中"),
    ("arms", "腕"),
    ("legs", "脚"),
    ("whole_body", "全身"),
    ("other", "その他"),
]


class AllergyReactionForm(forms.ModelForm):
    symptoms = forms.MultipleChoiceField(
        label="症状",
        choices=SYMPTOM_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    body_locations = forms.MultipleChoiceField(
        label="症状が出た場所",
        choices=BODY_LOCATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = AllergyReaction
        fields = (
            "onset_time",
            "minutes_after_eating",
            "symptoms",
            "body_locations",
            "other_symptom",
            "other_location",
            "visited_doctor",
            "medical_institution",
            "doctor_diagnosis",
            "doctor_instructions",
            "avoidance_instructed",
            "notes",
        )
        widgets = {
            "onset_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "form-control",
                }
            ),
            "minutes_after_eating": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "placeholder": "例：20",
                }
            ),
            "other_symptom": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "その他の症状",
                }
            ),
            "other_location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "その他の場所",
                }
            ),
            "medical_institution": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "doctor_diagnosis": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
            "doctor_instructions": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        if (
            "other" in cleaned_data.get("symptoms", [])
            and not cleaned_data.get("other_symptom")
        ):
            self.add_error(
                "other_symptom",
                "その他の症状を入力してください。",
            )

        return cleaned_data

class BabySettingsForm(forms.ModelForm):
    class Meta:
        model = Baby
        fields = [
            "name",
            "birth_date",
        ]
        labels = {
            "name": "子どもの名前",
            "birth_date": "生年月日",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "例：のい",
                    "autocomplete": "off",
                }
            ),
            "birth_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
        }

class BabyMemberAddForm(forms.Form):
    """既存ユーザーを共同管理者として追加するフォーム。"""

    username = forms.CharField(
        label="ユーザー名",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "例：papa",
                "autocomplete": "off",
                "autocapitalize": "none",
            }
        ),
    )

    can_edit = forms.BooleanField(
        label="食事記録や設定を編集できる",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    def __init__(
        self,
        *args,
        baby=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.baby = baby
        self.target_user = None

    def clean_username(self):
        username = (
            self.cleaned_data["username"]
            .strip()
        )

        User = get_user_model()

        try:
            user = User.objects.get(
                username__iexact=username,
                is_active=True,
            )
        except User.DoesNotExist as exc:
            raise ValidationError(
                "このユーザー名のアカウントは見つからない。"
            ) from exc

        if (
            self.baby
            and BabyMembership.objects.filter(
                baby=self.baby,
                user=user,
            ).exists()
        ):
            raise ValidationError(
                "このユーザーはすでに共同管理者として登録されている。"
            )

        self.target_user = user

        return username

    def save(self):
        if not self.is_valid():
            raise ValueError(
                "有効なフォームだけ保存できる。"
            )

        if self.baby is None:
            raise ValueError(
                "対象の子どもが指定されていない。"
            )

        return BabyMembership.objects.create(
            baby=self.baby,
            user=self.target_user,
            can_edit=self.cleaned_data["can_edit"],
        )

class BabyDeleteConfirmForm(forms.Form):
    confirm_name = forms.CharField(
        label="確認のため子どもの名前を入力",
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "off",
                "placeholder": "子どもの名前を入力",
            }
        ),
    )

    def __init__(
        self,
        *args,
        baby=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.baby = baby

    def clean_confirm_name(self):
        confirm_name = (
            self.cleaned_data["confirm_name"]
            .strip()
        )

        if (
            self.baby is None
            or confirm_name != self.baby.name
        ):
            raise ValidationError(
                "子どもの名前が一致しない。"
            )

        return confirm_name

class SupplementCreateForm(forms.ModelForm):
    class Meta:
        model = Supplement
        fields = (
            "name",
        )

        labels = {
            "name": "薬・サプリ名",
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "例：鉄剤",
                    "autocomplete": "off",
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        if Supplement.objects.filter(
            name__iexact=name,
        ).exists():
            raise ValidationError(
                "同じ名前の薬・サプリがすでに登録されている。"
            )

        return name

class FoodCreateForm(forms.ModelForm):
    class Meta:
        model = Food
        fields = (
            "name",
            "category",
            "feeding_group",
            "allergens",
            "show_in_first_year_list",
        )

        labels = {
            "name": "食材名",
            "category": "食材ジャンル",
            "feeding_group": "標準量の分類",
            "allergens": "含まれるアレルゲン",
            "show_in_first_year_list": (
                "食材チャレンジに表示する"
            ),
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "例：洋なし",
                    "autocomplete": "off",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "feeding_group": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "allergens": forms.CheckboxSelectMultiple(),
            "show_in_first_year_list": (
                forms.CheckboxInput()
            ),
        }

        help_texts = {
            "feeding_group": (
                "「今日の離乳食量」の集計に使う分類。"
            ),
            "allergens": (
                "該当するものがなければ選択不要。"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = (
            FoodCategory.objects
            .filter(is_active=True)
            .order_by(
                "display_order",
                "name",
            )
        )

        self.fields["feeding_group"].queryset = (
            FeedingGroup.objects
            .filter(is_active=True)
            .order_by(
                "display_order",
                "name",
            )
        )

        self.fields["allergens"].queryset = (
            Allergen.objects
            .filter(is_active=True)
            .order_by(
                "classification",
                "display_order",
                "name",
            )
        )

        self.fields[
            "show_in_first_year_list"
        ].initial = True

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        duplicate_exists = (
            Food.objects
            .filter(name__iexact=name)
            .exists()
        )

        if duplicate_exists:
            raise ValidationError(
                "同じ名前の食材がすでに登録されている。"
            )

        return name

class DishCreateForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = (
            "name",
            "category",
            "finished_amount_g",
        )
        labels = {
            "name": "料理名",
            "category": "料理ジャンル",
            "finished_amount_g": "完成量",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "例：鶏肉とかぼちゃのおかゆ",
                    "autocomplete": "off",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "finished_amount_g": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0.01",
                    "step": "0.01",
                    "inputmode": "decimal",
                    "placeholder": "例：200",
                }
            ),
        }
        help_texts = {
            "finished_amount_g": (
                "調理後に完成した料理全体の重量をgで入力する。"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = (
            DishCategory.objects
            .filter(is_active=True)
            .order_by(
                "display_order",
                "name",
            )
        )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        duplicate_dishes = Dish.objects.filter(
            name__iexact=name,
        )

        if self.instance and self.instance.pk:
            duplicate_dishes = duplicate_dishes.exclude(
                pk=self.instance.pk,
            )

        if duplicate_dishes.exists():
            raise ValidationError(
                "同じ名前の料理がすでに登録されている。"
            )

        return name

class CommercialProductCreateForm(
    forms.ModelForm
):
    class Meta:
        model = Dish

        fields = (
            "name",
            "commercial_brand",
            "recommended_from_month",
            "finished_amount_g",
            "source_url",
            "ingredient_data_verified",
            "ingredient_data_note",
        )

        labels = {
            "name": "商品名",
            "commercial_brand": "メーカー",
            "recommended_from_month": (
                "対象月齢"
            ),
            "finished_amount_g": (
                "内容量"
            ),
            "source_url": (
                "公式商品ページ"
            ),
            "ingredient_data_verified": (
                "材料割合確認済み"
            ),
            "ingredient_data_note": (
                "材料データの注記"
            ),
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "例："
                        "Gemüse mit Reis und Huhn"
                    ),
                    "autocomplete": "off",
                }
            ),
            "commercial_brand": (
                forms.Select(
                    attrs={
                        "class": "form-control",
                    }
                )
            ),
            "recommended_from_month": (
                forms.NumberInput(
                    attrs={
                        "class": "form-control",
                        "min": "4",
                        "max": "36",
                        "step": "1",
                        "placeholder": "例：6",
                    }
                )
            ),
            "finished_amount_g": (
                forms.NumberInput(
                    attrs={
                        "class": "form-control",
                        "min": "0.01",
                        "step": "0.01",
                        "inputmode": "decimal",
                        "placeholder": "例：190",
                    }
                )
            ),
            "source_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "https://..."
                    ),
                }
            ),
            "ingredient_data_verified": (
                forms.CheckboxInput()
            ),
            "ingredient_data_note": (
                forms.TextInput(
                    attrs={
                        "class": "form-control",
                        "placeholder": (
                            "例：主要材料のみ"
                            "割合が明記されている"
                        ),
                    }
                )
            ),
        }

        help_texts = {
            "finished_amount_g": (
                "商品の容器全体の内容量を"
                "gで入力する。"
            ),
            "recommended_from_month": (
                "「6か月頃から」なら6を入力する。"
            ),
            "ingredient_data_verified": (
                "公式ページまたは商品ラベルで"
                "割合を確認できた場合のみ"
                "チェックする。"
            ),
        }

    def clean_name(self):
        name = (
            self.cleaned_data["name"]
            .strip()
        )

        duplicate_products = (
            Dish.objects
            .filter(
                name__iexact=name,
                is_commercial_product=True,
            )
        )

        if (
            self.instance
            and self.instance.pk
        ):
            duplicate_products = (
                duplicate_products
                .exclude(
                    pk=self.instance.pk,
                )
            )

        if duplicate_products.exists():
            raise ValidationError(
                "同じ名前の市販品が"
                "すでに登録されています。"
            )

        return name

    def clean(self):
        cleaned_data = super().clean()

        brand = cleaned_data.get(
            "commercial_brand"
        )

        if not brand:
            self.add_error(
                "commercial_brand",
                "メーカーを選択してください。",
            )

        return cleaned_data

class CommercialBrandCreateForm(
    forms.ModelForm
):
    class Meta:
        model = CommercialBrand

        fields = (
            "name",
        )

        labels = {
            "name": "メーカー名",
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "例：dmBio、Alnatura、"
                        "和光堂"
                    ),
                    "autocomplete": "off",
                }
            ),
        }

    def clean_name(self):
        name = (
            self.cleaned_data["name"]
            .strip()
        )

        duplicate_brand = (
            CommercialBrand.objects
            .filter(
                name__iexact=name,
            )
        )

        if (
            self.instance
            and self.instance.pk
        ):
            duplicate_brand = (
                duplicate_brand
                .exclude(
                    pk=self.instance.pk,
                )
            )

        if duplicate_brand.exists():
            raise ValidationError(
                "同じ名前のメーカーが"
                "すでに登録されている。"
            )

        return name
    
class DishIngredientForm(forms.ModelForm):
    food_category = forms.ModelChoiceField(
        label="食材ジャンル",
        queryset=FoodCategory.objects.none(),
        required=False,
        empty_label="食材ジャンルを選択",
        widget=forms.Select(
            attrs={
                "class": (
                    "form-control "
                    "ingredient-food-category-select"
                ),
            }
        ),
    )

    food = FoodChoiceField(
        label="食材名",
        queryset=Food.objects.none(),
        required=False,
        empty_label="食材を選択",
        widget=CategoryDataSelect(
            attrs={
                "class": (
                    "form-control "
                    "ingredient-food-select"
                ),
            }
        ),
    )

    class Meta:
        model = DishIngredient
        fields = (
            "food_category",
            "food",
            "amount_g",
        )
        labels = {
            "amount_g": "使用量",
        }
        widgets = {
            "amount_g": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0.01",
                    "step": "0.01",
                    "inputmode": "decimal",
                    "placeholder": "例：30",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[
            "food_category"
        ].queryset = (
            FoodCategory.objects
            .filter(is_active=True)
            .order_by(
                "display_order",
                "name",
            )
        )

        self.fields["food"].queryset = (
            Food.objects
            .filter(is_active=True)
            .select_related("category")
            .order_by(
                "category__display_order",
                "category__name",
                "name",
            )
        )

        if (
            self.instance
            and self.instance.food_id
        ):
            self.fields[
                "food_category"
            ].initial = (
                self.instance.food.category_id
            )

    def clean(self):
        cleaned_data = super().clean()

        food_category = cleaned_data.get(
            "food_category"
        )
        food = cleaned_data.get("food")
        amount_g = cleaned_data.get("amount_g")

        row_has_input = bool(
            food_category
            or food
            or amount_g
        )

        if not row_has_input:
            return cleaned_data

        if food_category is None:
            self.add_error(
                "food_category",
                "食材ジャンルを選択してください。",
            )

        if food is None:
            self.add_error(
                "food",
                "食材を選択してください。",
            )

        if amount_g is None:
            self.add_error(
                "amount_g",
                "使用量を入力してください。",
            )

        if (
            food
            and food_category
            and food.category_id
            != food_category.id
        ):
            self.add_error(
                "food",
                "選択したジャンルに属する食材を選んでください。",
            )

        return cleaned_data

class BaseDishIngredientFormSet(
    BaseInlineFormSet
):
    def clean(self):
        super().clean()

        if any(
            form.errors
            for form in self.forms
        ):
            return

        ingredient_count = 0
        selected_food_ids = set()

        for form in self.forms:
            cleaned_data = getattr(
                form,
                "cleaned_data",
                {},
            )

            if not cleaned_data:
                continue

            if cleaned_data.get("DELETE"):
                continue

            food = cleaned_data.get("food")
            amount_g = cleaned_data.get(
                "amount_g"
            )

            if food is None and amount_g is None:
                continue

            if food is None:
                continue

            ingredient_count += 1

            if food.pk in selected_food_ids:
                form.add_error(
                    "food",
                    "同じ食材がすでに材料に追加されている。",
                )
            else:
                selected_food_ids.add(food.pk)

        if ingredient_count == 0:
            raise ValidationError(
                "少なくとも1つの材料を入力してください。"
            )

DishIngredientFormSet = inlineformset_factory(
    Dish,
    DishIngredient,
    form=DishIngredientForm,
    formset=BaseDishIngredientFormSet,
    extra=3,
    can_delete=True,
    max_num=30,
    validate_max=True,
)