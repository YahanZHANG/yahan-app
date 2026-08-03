from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from .models import Baby

from .models import (
    Allergen,
    AllergyReaction,
    Dish,
    DishCategory,
    DishIngredient,
    FeedingGroup,
    Food,
    FoodCategory,
    Meal,
    MealItem,
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
            option["attrs"][
                "data-category-id"
            ] = str(instance.category_id)

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
                "class": "form-control food-select",
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
                "class": "form-control dish-select",
            }
        ),
    )

    unit = forms.ChoiceField(
        choices=[
            (MealItem.Unit.GRAM, "g"),
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
                "class": "reaction-radio-input",
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
                    "class": "allergy-symptom-checkbox",
                }
            ),
        }

        labels = {
            "amount": "実際に食べた量(g)",
            "has_allergy_symptoms": "症状が出た",
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

        self.fields[
            "dish_category"
        ].queryset = (
            DishCategory.objects
            .filter(is_active=True)
            .order_by(
                "display_order",
                "name",
            )
        )

        if self.instance and self.instance.pk:
            self.fields[
                "item_type"
            ].initial = self.instance.item_type

            self.fields[
                "unit"
            ].initial = MealItem.Unit.GRAM

        else:
            self.fields[
                "item_type"
            ].initial = MealItem.ItemType.FOOD

            self.fields[
                "unit"
            ].initial = MealItem.Unit.GRAM

        if (
            self.instance
            and self.instance.food_id
        ):
            self.fields[
                "food_category"
            ].initial = (
                self.instance.food.category_id
            )

        if (
            self.instance
            and self.instance.dish_id
        ):
            self.fields[
                "dish_category"
            ].initial = (
                self.instance.dish.category_id
            )

        food_query = Food.objects.filter(
            is_active=True
        )

        if (
            self.instance
            and self.instance.food_id
        ):
            food_query = Food.objects.filter(
                Q(is_active=True)
                | Q(pk=self.instance.food_id)
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
            is_active=True
        )

        if (
            self.instance
            and self.instance.dish_id
        ):
            dish_query = Dish.objects.filter(
                Q(is_active=True)
                | Q(pk=self.instance.dish_id)
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

    def clean_unit(self):
        return MealItem.Unit.GRAM

    def clean(self):
        cleaned_data = super().clean()

        item_type = (
            cleaned_data.get("item_type")
            or MealItem.ItemType.FOOD
        )

        cleaned_data["item_type"] = item_type
        cleaned_data["unit"] = MealItem.Unit.GRAM

        food_category = cleaned_data.get(
            "food_category"
        )
        food = cleaned_data.get("food")

        dish_category = cleaned_data.get(
            "dish_category"
        )
        dish = cleaned_data.get("dish")

        if item_type == MealItem.ItemType.FOOD:
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

        elif item_type == MealItem.ItemType.DISH:
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

        return cleaned_data

class BaseMealItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(form.errors for form in self.forms):
            return

        active_item_count = 0
        selected_items = set()

        for form in self.forms:
            cleaned_data = getattr(form, "cleaned_data", {})

            if not cleaned_data:
                continue

            if cleaned_data.get("DELETE"):
                continue

            item_type = cleaned_data.get("item_type")

            if not item_type:
                continue

            food = cleaned_data.get("food")
            dish = cleaned_data.get("dish")

            if item_type == MealItem.ItemType.FOOD and food:
                selected_key = ("food", food.pk)
                selected_field = "food"
                active_item_count += 1

            elif item_type == MealItem.ItemType.DISH and dish:
                selected_key = ("dish", dish.pk)
                selected_field = "dish"
                active_item_count += 1

            else:
                continue

            if selected_key in selected_items:
                form.add_error(
                    selected_field,
                    "同じ食材・料理がこの食事内ですでに選択されている。",
                )
            else:
                selected_items.add(selected_key)

        if active_item_count == 0:
            raise ValidationError(
                "少なくとも1件の食材または料理を入力してください。"
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

        if Dish.objects.filter(
            name__iexact=name,
        ).exists():
            raise ValidationError(
                "同じ名前の料理がすでに登録されている。"
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