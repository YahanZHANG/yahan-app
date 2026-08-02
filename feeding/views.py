from datetime import date
from django.contrib.auth.decorators import login_required

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from collections import defaultdict
from decimal import Decimal

from .forms import (
    AllergyReactionForm,
    BabySettingsForm,
    MealForm,
    MealItemCreateFormSet,
    MealItemEditFormSet,
)

from .models import (
    Allergen,
    AllergyReaction,
    AllergyReactionPhoto,
    Baby,
    FeedingGuideline,
    Food,
    FoodCategory,
    Meal,
    MealItem,
)


def get_current_baby():
    """
    現段階では、最初に登録された赤ちゃんを使用する。

    後の段階で家族ログインや複数の赤ちゃんに
    対応できるように変更する。
    """
    return Baby.objects.order_by("id").first()

def calculate_age_in_months(birth_date, target_date):
    """指定日時点の満月齢を計算する。"""
    months = (
        (target_date.year - birth_date.year) * 12
        + target_date.month
        - birth_date.month
    )

    if target_date.day < birth_date.day:
        months -= 1

    return max(months, 0)

def get_feeding_stage(age_months):
    """月齢から離乳食ステージと標準食事回数を返す。"""
    if age_months < 5:
        return {
            "name": "離乳食開始前",
            "meal_guide": "開始時期を待つ",
            "recommended_meals": 0,
            "class_name": "before",
        }

    if age_months <= 6:
        return {
            "name": "離乳初期",
            "meal_guide": "1日1回が目安",
            "recommended_meals": 1,
            "class_name": "early",
        }

    if age_months <= 8:
        return {
            "name": "離乳中期",
            "meal_guide": "1日2回が目安",
            "recommended_meals": 2,
            "class_name": "middle",
        }

    if age_months <= 11:
        return {
            "name": "離乳後期",
            "meal_guide": "1日3回が目安",
            "recommended_meals": 3,
            "class_name": "late",
        }

    return {
        "name": "離乳完了期",
        "meal_guide": "1日3回が目安",
        "recommended_meals": 3,
        "class_name": "complete",
    }

def get_food_meal_ids(food, baby):
    """
    食材を直接食べた食事と、
    料理の材料として食べた食事のIDを返す。
    """
    direct_ids = set(
        food.meal_items
        .filter(meal__baby=baby)
        .values_list("meal_id", flat=True)
    )

    dish_ids = set(
        food.meal_item_ingredient_snapshots
        .filter(meal_item__meal__baby=baby)
        .values_list("meal_item__meal_id", flat=True)
    )

    return direct_ids | dish_ids

def get_allergen_meal_ids(allergen, baby):
    """
    アレルゲンを含む食材を直接食べた食事と、
    料理の材料として食べた食事のIDを返す。
    """
    direct_ids = set(
        MealItem.objects
        .filter(
            meal__baby=baby,
            food__allergens=allergen,
        )
        .values_list("meal_id", flat=True)
    )

    dish_ids = set(
        MealItem.objects
        .filter(
            meal__baby=baby,
            ingredient_snapshots__food__allergens=allergen,
        )
        .values_list("meal_id", flat=True)
    )

    return direct_ids | dish_ids

def get_exposure_status(exposure_count):
    """摂取回数から共通ステータスを返す。"""
    if exposure_count == 0:
        return {
            "status": "not-yet",
            "label": "まだ",
            "icon": "－",
        }

    if exposure_count < 3:
        return {
            "status": "tried",
            "label": "食べた",
            "icon": "○",
        }

    return {
        "status": "familiar",
        "label": "食べ慣れた",
        "icon": "✓",
    }

def get_daily_guideline_summary(
    meals,
    age_months,
    recommended_meals,
):
    """
    その日の全食事を合計し、
    月齢別の1日分の目安量と比較する。

    集計対象：
    ・単一食材のg記録
    ・料理の材料スナップショット
    """

    guidelines = (
        FeedingGuideline.objects
        .filter(
            min_age_months__lte=age_months,
            max_age_months__gte=age_months,
        )
        .select_related("feeding_group")
        .order_by("display_order")
    )

    actual_amounts = defaultdict(
        lambda: Decimal("0")
    )

    excluded_items = []

    def add_food_amount(
        food,
        amount,
        display_name,
    ):
        """
        食材の食品群に、摂取量を加算する。
        集計できない場合は除外一覧へ追加する。
        """

        if amount is None:
            excluded_items.append(
                {
                    "name": display_name,
                    "reason": "材料量が未設定",
                }
            )
            return

        if not food or not food.feeding_group:
            excluded_items.append(
                {
                    "name": display_name,
                    "reason": "食品群未設定",
                }
            )
            return

        group_code = food.feeding_group.code

        if group_code == "other":
            excluded_items.append(
                {
                    "name": display_name,
                    "reason": "比較対象外",
                }
            )
            return

        actual_amounts[group_code] += amount

    for meal in meals:
        items = (
            meal.items
            .select_related(
                "food",
                "food__feeding_group",
                "dish",
            )
            .prefetch_related(
                "ingredient_snapshots__food__feeding_group",
            )
            .order_by("display_order", "id")
        )

        for item in items:
            # g以外は現段階では換算しない
            if item.unit != MealItem.Unit.GRAM:
                excluded_items.append(
                    {
                        "name": item.item_name,
                        "reason": (
                            f"{item.get_unit_display()}単位"
                        ),
                    }
                )
                continue

            # 単一食材
            if (
                item.item_type
                == MealItem.ItemType.FOOD
            ):
                add_food_amount(
                    food=item.food,
                    amount=item.amount,
                    display_name=item.item_name,
                )
                continue

            # 料理
            if (
                item.item_type
                == MealItem.ItemType.DISH
            ):
                snapshots = list(
                    item.ingredient_snapshots.all()
                )

                if not snapshots:
                    excluded_items.append(
                        {
                            "name": item.item_name,
                            "reason": (
                                "料理材料の履歴がない"
                            ),
                        }
                    )
                    continue

                for snapshot in snapshots:
                    add_food_amount(
                        food=snapshot.food,
                        amount=snapshot.amount_g,
                        display_name=(
                            f"{item.item_name}："
                            f"{snapshot.food.name}"
                        ),
                    )

    protein_group_codes = {
        "fish",
        "meat",
        "tofu",
        "egg",
        "dairy",
    }

    main_rows = []
    protein_rows = []

    for guideline in guidelines:
        group_code = guideline.feeding_group.code
        actual = actual_amounts[group_code]

        comparison_available = (
            guideline.unit
            == FeedingGuideline.Unit.GRAM
            and group_code
            not in protein_group_codes
        )

        daily_minimum = None
        daily_maximum = None
        percent = 0
        amount_status = "none"

        if comparison_available:
            if guideline.minimum_amount is not None:
                daily_minimum = (
                    guideline.minimum_amount
                    * recommended_meals
                )

            if guideline.maximum_amount is not None:
                daily_maximum = (
                    guideline.maximum_amount
                    * recommended_meals
                )

            if daily_maximum and daily_maximum > 0:
                percent = min(
                    round(
                        float(
                            actual / daily_maximum
                        )
                        * 100
                    ),
                    100,
                )

            if actual == 0:
                amount_status = "none"

            elif (
                daily_minimum is not None
                and actual < daily_minimum
            ):
                amount_status = "below"

            elif (
                daily_maximum is not None
                and actual > daily_maximum
            ):
                amount_status = "above"

            else:
                amount_status = "within"

        row = {
            "guideline": guideline,
            "actual": actual,
            "daily_minimum": daily_minimum,
            "daily_maximum": daily_maximum,
            "percent": percent,
            "amount_status": amount_status,
            "comparison_available": comparison_available,
        }

        if group_code in protein_group_codes:
            protein_rows.append(row)
        else:
            main_rows.append(row)

    return {
        "main_rows": main_rows,
        "protein_rows": protein_rows,
        "excluded_items": excluded_items,
        "excluded_item_count": len(
            excluded_items
        ),
        "recommended_meals": recommended_meals,
    }

def parse_selected_date(date_value):
    if not date_value:
        return timezone.localdate()

    try:
        return date.fromisoformat(date_value)
    except ValueError:
        return timezone.localdate()

@login_required
def today(request):
    baby = get_current_baby()
    today_date = timezone.localdate()

    meal_cards = []
    meals_by_number = {}
    today_item_count = 0

    age_months = None
    feeding_stage = None
    daily_guideline_summary = None

    total_food_count = 0
    eaten_food_count = 0
    food_progress_percent = 0

    total_allergen_count = 0
    eaten_allergen_count = 0
    allergen_progress_percent = 0

    recent_first_foods = []

    if baby:
        age_months = calculate_age_in_months(
            baby.birth_date,
            today_date,
        )

        feeding_stage = get_feeding_stage(age_months)

        meals = list(
            Meal.objects
            .filter(
                baby=baby,
                date=today_date,
            )
            .annotate(
                item_count_value=Count("items"),
            )
            .order_by("meal_number")
        )

        meals_by_number = {
            meal.meal_number: meal
            for meal in meals
        }

        today_item_count = sum(
            meal.item_count_value
            for meal in meals
        )

        recommended_meals = feeding_stage[
            "recommended_meals"
        ]

        if (
            7 <= age_months <= 18
            and recommended_meals > 0
        ):
            daily_guideline_summary = (
                get_daily_guideline_summary(
                    meals=meals,
                    age_months=age_months,
                    recommended_meals=recommended_meals,
                )
            )

        # --------------------------------------------------
        # 食材チャレンジ
        # --------------------------------------------------

        target_foods = Food.objects.filter(
            is_active=True,
            show_in_first_year_list=True,
        )

        total_food_count = target_foods.count()

        eaten_food_count = (
            target_foods
            .filter(
                Q(
                    meal_items__meal__baby=baby,
                )
                | Q(
                    meal_item_ingredient_snapshots__meal_item__meal__baby=baby,
                )
            )
            .distinct()
            .count()
        )
                
        if total_food_count:
            food_progress_percent = round(
                eaten_food_count
                / total_food_count
                * 100
            )

        # --------------------------------------------------
        # アレルゲン進捗
        # --------------------------------------------------

        active_allergens = (
            Allergen.objects
            .filter(is_active=True)
        )

        total_allergen_count = (
            active_allergens.count()
        )

        eaten_allergen_count = (
            active_allergens
            .filter(
                Q(
                    foods__meal_items__meal__baby=baby,
                )
                | Q(
                    foods__meal_item_ingredient_snapshots__meal_item__meal__baby=baby,
                )
            )
            .distinct()
            .count()
        )

        if total_allergen_count:
            allergen_progress_percent = round(
                eaten_allergen_count
                / total_allergen_count
                * 100
            )

        # --------------------------------------------------
        # 最近初めて食べた食材
        # --------------------------------------------------

        food_first_dates = (
            target_foods
            .select_related("category")
            .annotate(
                first_direct_date=Min(
                    "meal_items__meal__date",
                    filter=Q(
                        meal_items__meal__baby=baby,
                    ),
                ),
                first_dish_date=Min(
                    "meal_item_ingredient_snapshots__"
                    "meal_item__meal__date",
                    filter=Q(
                        meal_item_ingredient_snapshots__meal_item__meal__baby=baby,
                    ),
                ),
            )
        )

        recent_candidates = []

        for food in food_first_dates:
            dates = [
                value
                for value in [
                    food.first_direct_date,
                    food.first_dish_date,
                ]
                if value is not None
            ]

            if not dates:
                continue

            recent_candidates.append(
                {
                    "food": food,
                    "first_date": min(dates),
                }
            )

        recent_candidates.sort(
            key=lambda item: item["first_date"],
            reverse=True,
        )

        recent_first_foods = (
            recent_candidates[:5]
        )
    
    for meal_number, meal_label in Meal.MealNumber.choices:
        meal = meals_by_number.get(meal_number)

        meal_cards.append(
            {
                "number": meal_number,
                "label": meal_label,
                "meal": meal,
                "item_count": (
                    meal.item_count_value
                    if meal
                    else 0
                ),
            }
        )
    
    context = {
        "baby": baby,
        "today_date": today_date,
        "age_months": age_months,
        "feeding_stage": feeding_stage,
        "meal_cards": meal_cards,
        "today_item_count": today_item_count,
        "total_food_count": total_food_count,
        "eaten_food_count": eaten_food_count,
        "food_progress_percent": food_progress_percent,
        "daily_guideline_summary": daily_guideline_summary,
        "total_allergen_count": total_allergen_count,
        "eaten_allergen_count": eaten_allergen_count,
        "allergen_progress_percent": allergen_progress_percent,
        "recent_first_foods": recent_first_foods,
    }

    return render(
        request,
        "feeding/today.html",
        context,
    )

@login_required
def food_list(request):
    baby = get_current_baby()

    categories = (
        FoodCategory.objects
        .filter(is_active=True)
        .prefetch_related(
            "foods__meal_items",
            "foods__meal_item_ingredient_snapshots",
        )
        .order_by("display_order", "name")
    )

    category_cards = []

    for category in categories:
        food_cards = []

        foods = (
            category.foods
            .filter(
                is_active=True,
                show_in_first_year_list=True,
            )
            .order_by("name")
        )

        for food in foods:
            direct_meal_ids = set()

            if baby:
                direct_meal_ids = set(
                    food.meal_items
                    .filter(meal__baby=baby)
                    .values_list("meal_id", flat=True)
                )

            dish_meal_ids = set()

            if baby:
                dish_meal_ids = set(
                    food.meal_item_ingredient_snapshots
                    .filter(meal_item__meal__baby=baby)
                    .values_list("meal_item__meal_id", flat=True)
                )

            meal_ids = direct_meal_ids | dish_meal_ids
            eaten_count = len(meal_ids)

            if eaten_count == 0:
                status = "not-yet"
                status_label = "まだ"
                status_icon = "－"
            elif eaten_count < 3:
                status = "tried"
                status_label = "食べた"
                status_icon = "○"
            else:
                status = "familiar"
                status_label = "食べ慣れた"
                status_icon = "✓"

            food_cards.append(
                {
                    "food": food,
                    "count": eaten_count,
                    "status": status,
                    "status_label": status_label,
                    "status_icon": status_icon,
                }
            )

        eaten_food_count = sum(
            1
            for card in food_cards
            if card["count"] > 0
        )

        category_cards.append(
            {
                "category": category,
                "foods": food_cards,
                "eaten_count": eaten_food_count,
                "total_count": len(food_cards),
            }
        )

    context = {
        "baby": baby,
        "category_cards": category_cards,
    }

    return render(
        request,
        "feeding/food_list.html",
        context,
    )

@login_required
def food_detail(request, food_id):
    baby = get_current_baby()

    food = get_object_or_404(
        Food.objects.select_related("category"),
        pk=food_id,
        is_active=True,
    )

    history = []

    if baby:
        direct_items = (
            MealItem.objects
            .filter(
                meal__baby=baby,
                food=food,
            )
            .select_related("meal")
            .order_by("-meal__date", "-meal__meal_number")
        )

        for item in direct_items:
            history.append(
                {
                    "date": item.meal.date,
                    "meal_number": item.meal.get_meal_number_display(),
                    "source": food.name,
                    "amount": item.amount,
                    "unit": item.get_unit_display(),
                    "reaction": item.get_reaction_display(),
                    "meal_id": item.meal_id,
                }
            )

        dish_items = (
            MealItem.objects
            .filter(
                meal__baby=baby,
                ingredient_snapshots__food=food,
            )
            .select_related("meal", "dish")
            .distinct()
            .order_by("-meal__date", "-meal__meal_number")
        )

        for item in dish_items:
            history.append(
                {
                    "date": item.meal.date,
                    "meal_number": item.meal.get_meal_number_display(),
                    "source": (
                        f"{item.dish.name}に含まれていた"
                        if item.dish
                        else "料理に含まれていた"
                    ),
                    "amount": None,
                    "unit": "",
                    "reaction": item.get_reaction_display(),
                    "meal_id": item.meal_id,
                }
            )

    history.sort(
        key=lambda entry: (
            entry["date"],
            entry["meal_id"],
        ),
        reverse=True,
    )

    unique_meal_ids = {
        entry["meal_id"]
        for entry in history
    }

    eaten_count = len(unique_meal_ids)

    if eaten_count == 0:
        status = "not-yet"
        status_label = "まだ"
        status_icon = "－"
    elif eaten_count < 3:
        status = "tried"
        status_label = "食べた"
        status_icon = "○"
    else:
        status = "familiar"
        status_label = "食べ慣れた"
        status_icon = "✓"

    first_date = (
        min(entry["date"] for entry in history)
        if history
        else None
    )

    last_date = (
        max(entry["date"] for entry in history)
        if history
        else None
    )

    context = {
        "food": food,
        "history": history,
        "eaten_count": eaten_count,
        "status": status,
        "status_label": status_label,
        "status_icon": status_icon,
        "first_date": first_date,
        "last_date": last_date,
    }

    return render(
        request,
        "feeding/food_detail.html",
        context,
    )

@login_required
def meal_edit(request, meal_number):
    valid_numbers = {
        number
        for number, _ in Meal.MealNumber.choices
    }

    if meal_number not in valid_numbers:
        messages.error(
            request,
            "食事番号が正しくない。",
        )
        return redirect("feeding:today")

    baby = get_current_baby()

    if baby is None:
        messages.error(
            request,
            "先に管理画面から赤ちゃんを登録してください。",
        )
        return redirect("feeding:today")

    meal_id = request.POST.get("meal_id")

    if meal_id:
        meal = get_object_or_404(
            Meal,
            pk=meal_id,
            baby=baby,
            meal_number=meal_number,
        )
    else:
        selected_date = parse_selected_date(
            request.GET.get("date")
        )

        meal = (
            Meal.objects
            .filter(
                baby=baby,
                date=selected_date,
                meal_number=meal_number,
            )
            .first()
        )

        if meal is None:
            meal = Meal(
                baby=baby,
                date=selected_date,
                meal_number=meal_number,
            )

    is_new = meal.pk is None

    if request.method == "POST":
        meal_form = MealForm(
            request.POST,
            instance=meal,
        )

        formset_class = (
            MealItemCreateFormSet
            if is_new
            else MealItemEditFormSet
        )

        item_formset = formset_class(
            request.POST,
            instance=meal,
            prefix="items",
        )

        if meal_form.is_valid() and item_formset.is_valid():
            selected_date = meal_form.cleaned_data["date"]

            duplicate_meals = Meal.objects.filter(
                baby=baby,
                date=selected_date,
                meal_number=meal_number,
            )

            if meal.pk:
                duplicate_meals = duplicate_meals.exclude(
                    pk=meal.pk
                )

            if duplicate_meals.exists():
                meal_form.add_error(
                    "date",
                    (
                        "この日付の"
                        f"{meal.get_meal_number_display()}"
                        "はすでに記録されている。"
                    ),
                )
            else:
                with transaction.atomic():
                    saved_meal = meal_form.save(
                        commit=False
                    )
                    saved_meal.baby = baby
                    saved_meal.meal_number = meal_number
                    saved_meal.save()

                    item_formset.instance = saved_meal

                    # deleted_objectsを取得できる状態にする。
                    item_formset.save(commit=False)

                    for deleted_item in item_formset.deleted_objects:
                        deleted_item.delete()

                    symptom_item_ids = []
                    display_order = 10

                    for item_form in item_formset.forms:
                        cleaned_data = getattr(
                            item_form,
                            "cleaned_data",
                            {},
                        )

                        if not cleaned_data:
                            continue

                        if cleaned_data.get("DELETE"):
                            continue

                        if (
                            item_form.instance.pk is None
                            and not item_form.has_changed()
                        ):
                            continue

                        item = item_form.save(
                            commit=False
                        )
                        item.meal = saved_meal
                        item.display_order = display_order

                        is_new_item = item.pk is None

                        selection_changed = (
                            is_new_item
                            or "item_type" in item_form.changed_data
                            or "food" in item_form.changed_data
                            or "dish" in item_form.changed_data
                            or "amount" in item_form.changed_data
                            or "unit" in item_form.changed_data
                        )

                        snapshot_missing = (
                            not is_new_item
                            and item.item_type
                            == MealItem.ItemType.DISH
                            and not item
                            .ingredient_snapshots
                            .exists()
                        )

                        item.save()

                        if item.has_allergy_symptoms:
                            symptom_item_ids.append(item.pk)
                        else:
                            AllergyReaction.objects.filter(
                                meal_item=item
                            ).delete()

                        if (
                            selection_changed
                            or snapshot_missing
                        ):
                            item.create_ingredient_snapshot()

                        display_order += 10

                    messages.success(
                        request,
                        (
                            f"{saved_meal.date:%Y年%m月%d日}の"
                            f"{saved_meal.get_meal_number_display()}を"
                            "保存した。"
                        ),
                    )

                    if symptom_item_ids:
                        request.session["pending_symptom_item_ids"] = (
                            symptom_item_ids[1:]
                        )

                        return redirect(
                            "feeding:allergy_reaction_edit",
                            meal_item_id=symptom_item_ids[0],
                        )

                    edit_url = reverse(
                        "feeding:meal_edit",
                        args=[meal_number],
                    )

                    return redirect(
                        f"{edit_url}?date="
                        f"{saved_meal.date.isoformat()}"
                    )

    else:
        meal_form = MealForm(
            instance=meal,
            initial={
                "date": meal.date,
            },
        )

        formset_class = (
            MealItemCreateFormSet
            if is_new
            else MealItemEditFormSet
        )

        item_formset = formset_class(
            instance=meal,
            prefix="items",
        )

    context = {
        "baby": baby,
        "meal": meal,
        "meal_form": meal_form,
        "item_formset": item_formset,
        "meal_number": meal_number,
        "meal_label": Meal.MealNumber(
            meal_number
        ).label,
        "is_new": is_new,
        "set_device_date": (
            request.method == "GET"
            and is_new
            and not request.GET.get("date")
        ),
    }

    return render(
        request,
        "feeding/meal_form.html",
        context,
    )

@login_required
@require_POST
def meal_delete(request, meal_number):
    baby = get_current_baby()

    if baby is None:
        return redirect("feeding:today")

    meal = get_object_or_404(
        Meal,
        pk=request.POST.get("meal_id"),
        baby=baby,
        meal_number=meal_number,
    )

    meal_description = str(meal)
    meal.delete()

    messages.success(
        request,
        f"{meal_description}を削除した。",
    )

    return redirect("feeding:today")

@login_required
def allergen_list(request):
    baby = get_current_baby()

    required_cards = []
    recommended_cards = []

    allergens = (
        Allergen.objects
        .filter(is_active=True)
        .order_by(
            "classification",
            "display_order",
            "name",
        )
    )

    eaten_allergen_count = 0
    total_allergen_count = allergens.count()

    for allergen in allergens:
        meal_ids = set()

        if baby:
            meal_ids = get_allergen_meal_ids(
                allergen,
                baby,
            )

        exposure_count = len(meal_ids)
        status_data = get_exposure_status(
            exposure_count
        )

        if exposure_count > 0:
            eaten_allergen_count += 1

        card = {
            "allergen": allergen,
            "count": exposure_count,
            **status_data,
        }

        if (
            allergen.classification
            == Allergen.Classification.REQUIRED
        ):
            required_cards.append(card)
        else:
            recommended_cards.append(card)

    progress_percent = 0

    if total_allergen_count:
        progress_percent = round(
            eaten_allergen_count
            / total_allergen_count
            * 100
        )

    context = {
        "baby": baby,
        "required_cards": required_cards,
        "recommended_cards": recommended_cards,
        "eaten_allergen_count": eaten_allergen_count,
        "total_allergen_count": total_allergen_count,
        "progress_percent": progress_percent,
    }

    return render(
        request,
        "feeding/allergen_list.html",
        context,
    )

@login_required
def allergen_detail(request, allergen_id):
    baby = get_current_baby()

    allergen = get_object_or_404(
        Allergen,
        pk=allergen_id,
        is_active=True,
    )

    history = []
    related_foods = []

    if baby:
        direct_items = (
            MealItem.objects
            .filter(
                meal__baby=baby,
                food__allergens=allergen,
            )
            .select_related(
                "meal",
                "food",
                "food__category",
            )
            .distinct()
        )

        for item in direct_items:
            history.append(
                {
                    "date": item.meal.date,
                    "meal_number": (
                        item.meal
                        .get_meal_number_display()
                    ),
                    "meal_id": item.meal_id,
                    "food": item.food,
                    "source": item.food.name,
                    "amount": item.amount,
                    "unit": item.get_unit_display(),
                    "reaction": (
                        item.get_reaction_display()
                    ),
                    "is_dish": False,
                }
            )

        dish_items = (
            MealItem.objects
            .filter(
                meal__baby=baby,
                ingredient_snapshots__food__allergens=allergen,
            )
            .select_related(
                "meal",
                "dish",
            )
            .prefetch_related(
                "ingredient_snapshots__food__category",
                "ingredient_snapshots__food__allergens",
            )
            .distinct()
        )

        for item in dish_items:
            matching_foods = [
                snapshot.food
                for snapshot in (
                    item.ingredient_snapshots.all()
                )
                if snapshot.food.allergens.filter(
                    pk=allergen.pk
                ).exists()
            ]

            food_names = "、".join(
                food.name
                for food in matching_foods
            )

            history.append(
                {
                    "date": item.meal.date,
                    "meal_number": (
                        item.meal
                        .get_meal_number_display()
                    ),
                    "meal_id": item.meal_id,
                    "food": None,
                    "source": (
                        item.dish.name
                        if item.dish
                        else "料理"
                    ),
                    "ingredient_names": food_names,
                    "amount": item.amount,
                    "unit": item.get_unit_display(),
                    "reaction": (
                        item.get_reaction_display()
                    ),
                    "is_dish": True,
                }
            )

        related_foods = list(
            Food.objects
            .filter(
                allergens=allergen,
                is_active=True,
            )
            .select_related("category")
            .distinct()
            .order_by(
                "category__display_order",
                "name",
            )
        )

    history.sort(
        key=lambda entry: (
            entry["date"],
            entry["meal_id"],
        ),
        reverse=True,
    )

    unique_meal_ids = {
        entry["meal_id"]
        for entry in history
    }

    exposure_count = len(unique_meal_ids)
    status_data = get_exposure_status(
        exposure_count
    )

    first_date = None
    last_date = None

    if history:
        history_dates = [
            entry["date"]
            for entry in history
        ]

        first_date = min(history_dates)
        last_date = max(history_dates)

    context = {
        "allergen": allergen,
        "history": history,
        "related_foods": related_foods,
        "exposure_count": exposure_count,
        "first_date": first_date,
        "last_date": last_date,
        **status_data,
    }

    return render(
        request,
        "feeding/allergen_detail.html",
        context,
    )

@login_required
def allergy_reaction_edit(request, meal_item_id):
    baby = get_current_baby()

    meal_item = get_object_or_404(
        MealItem.objects.select_related(
            "meal",
            "meal__baby",
            "food",
            "dish",
        ),
        pk=meal_item_id,
        meal__baby=baby,
    )

    reaction, _ = AllergyReaction.objects.get_or_create(
        meal_item=meal_item
    )

    if request.method == "POST":
        form = AllergyReactionForm(
            request.POST,
            instance=reaction,
        )

        uploaded_photos = request.FILES.getlist("photos")

        if form.is_valid():
            with transaction.atomic():
                saved_reaction = form.save()

                for photo in uploaded_photos:
                    AllergyReactionPhoto.objects.create(
                        reaction=saved_reaction,
                        image=photo,
                    )

                meal_item.has_allergy_symptoms = True
                meal_item.save(
                    update_fields=[
                        "has_allergy_symptoms",
                        "updated_at",
                    ]
                )

            messages.success(
                request,
                "アレルギー症状の詳細を保存した。",
            )

            pending_ids = request.session.get(
                "pending_symptom_item_ids",
                [],
            )

            if pending_ids:
                next_id = pending_ids.pop(0)
                request.session[
                    "pending_symptom_item_ids"
                ] = pending_ids

                return redirect(
                    "feeding:allergy_reaction_edit",
                    meal_item_id=next_id,
                )

            return redirect("feeding:allergen_list")

    else:
        form = AllergyReactionForm(
            instance=reaction
        )

    context = {
        "meal_item": meal_item,
        "reaction": reaction,
        "form": form,
        "allergen_names": meal_item.allergen_names,
    }

    return render(
        request,
        "feeding/allergy_reaction_form.html",
        context,
    )

@login_required
@require_POST
def allergy_reaction_delete(request, meal_item_id):
    baby = get_current_baby()

    meal_item = get_object_or_404(
        MealItem,
        pk=meal_item_id,
        meal__baby=baby,
    )

    AllergyReaction.objects.filter(
        meal_item=meal_item
    ).delete()

    meal_item.has_allergy_symptoms = False
    meal_item.save(
        update_fields=[
            "has_allergy_symptoms",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "症状記録を削除した。",
    )

    return redirect(
        "feeding:meal_edit",
        meal_number=meal_item.meal.meal_number,
    )

@login_required
@require_POST
def allergy_photo_delete(request, photo_id):
    baby = get_current_baby()

    photo = get_object_or_404(
        AllergyReactionPhoto,
        pk=photo_id,
        reaction__meal_item__meal__baby=baby,
    )

    meal_item_id = photo.reaction.meal_item_id
    photo.image.delete(save=False)
    photo.delete()

    messages.success(
        request,
        "写真を削除した。",
    )

    return redirect(
        "feeding:allergy_reaction_edit",
        meal_item_id=meal_item_id,
    )


@login_required
def settings_view(request):
    baby = get_current_baby()

    if baby is None:
        messages.error(
            request,
            "子どもの情報がまだ登録されていない。",
        )
        return redirect("feeding:today")

    if request.method == "POST":
        form = BabySettingsForm(
            request.POST,
            instance=baby,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "設定を保存した。",
            )

            return redirect(
                "feeding:settings",
            )
    else:
        form = BabySettingsForm(
            instance=baby,
        )

    context = {
        "baby": baby,
        "form": form,
    }

    return render(
        request,
        "feeding/settings.html",
        context,
    )