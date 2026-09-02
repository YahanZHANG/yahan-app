from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.db.models import Prefetch


from .models import (
    Appliance,
    Ingredient,
    MoodTag,
    NutritionTag,
    Recipe,
    RecipeIngredient,
    RecipePreference,
)



def home(request):
    return render(request, "recipes/home.html")


def recipe_list(request, appliance_type):

    appliance = get_object_or_404(
        Appliance,
        appliance_type=appliance_type,
    )

    recipes = (
        Recipe.objects
        .filter(
            appliance=appliance,
            is_active=True,
            verified_for_model=True,
        )
        .prefetch_related(
            "recipe_ingredients__ingredient",
            "mood_tags",
            "nutrition_tags",
        )
        .order_by("name")
    )

    context = {
        "appliance": appliance,
        "recipes": recipes,
    }

    return render(
        request,
        "recipes/recipe_list.html",
        context,
    )

def recipe_detail(request, pk):

    recipe = get_object_or_404(
        Recipe.objects
        .select_related("appliance")
        .prefetch_related(
            "recipe_ingredients__ingredient",
            "mood_tags",
            "nutrition_tags",
        ),
        pk=pk,
        is_active=True,
        verified_for_model=True,
    )

    food_ingredients = []
    seasonings = []

    for item in recipe.recipe_ingredients.all():
        if item.ingredient.is_seasoning:
            seasonings.append(item)
        else:
            food_ingredients.append(item)

    preference = None

    if request.user.is_authenticated:
        preference_obj = (
            RecipePreference.objects
            .filter(
                user=request.user,
                recipe=recipe,
            )
            .first()
        )

        if preference_obj:
            preference = preference_obj.preference

    context = {
        "recipe": recipe,
        "food_ingredients": food_ingredients,
        "seasonings": seasonings,
        "preference": preference,
    }

    return render(
        request,
        "recipes/recipe_detail.html",
        context,
    )


@login_required
@require_POST
def toggle_preference(request, pk):

    recipe = get_object_or_404(
        Recipe,
        pk=pk,
        is_active=True,
        verified_for_model=True,
    )

    preference = request.POST.get("preference")

    if preference not in {
        "favorite",
        "dislike",
    }:
        return JsonResponse(
            {
                "ok": False,
                "error": "invalid preference",
            },
            status=400,
        )

    existing = (
        RecipePreference.objects
        .filter(
            user=request.user,
            recipe=recipe,
        )
        .first()
    )

    # 同じボタンをもう一度押した場合は解除
    if (
        existing
        and existing.preference == preference
    ):
        existing.delete()

        return JsonResponse(
            {
                "ok": True,
                "preference": None,
            }
        )

    # ★ → ×、または × → ★ の場合は状態を変更
    RecipePreference.objects.update_or_create(
        user=request.user,
        recipe=recipe,
        defaults={
            "preference": preference,
        },
    )

    return JsonResponse(
        {
            "ok": True,
            "preference": preference,
        }
    )


@login_required
def my_recipes(request):

    favorites = (
        Recipe.objects
        .filter(
            preferences__user=request.user,
            preferences__preference="favorite",
            is_active=True,
            verified_for_model=True,
        )
        .select_related("appliance")
        .prefetch_related(
            "recipe_ingredients__ingredient",
        )
        .order_by("name")
    )

    dislikes = (
        Recipe.objects
        .filter(
            preferences__user=request.user,
            preferences__preference="dislike",
            is_active=True,
            verified_for_model=True,
        )
        .select_related("appliance")
        .prefetch_related(
            "recipe_ingredients__ingredient",
        )
        .order_by("name")
    )

    context = {
        "favorites": favorites,
        "dislikes": dislikes,
    }

    return render(
        request,
        "recipes/my_recipes.html",
        context,
    )


def find_by_ingredients(request):

    # -----------------------------
    # 選択肢として表示する食材
    # -----------------------------

    ingredients = (
        Ingredient.objects
        .filter(
            is_seasoning=False,
        )
        .order_by(
            "category",
            "name",
        )
    )


    # GETで選択された食材ID
    selected_ids = request.GET.getlist(
        "ingredients"
    )

    selected_ids = [
        int(ingredient_id)
        for ingredient_id in selected_ids
        if ingredient_id.isdigit()
    ]


    results = []


    if selected_ids:

        selected_id_set = set(
            selected_ids
        )


        recipes = (
            Recipe.objects
            .filter(
                is_active=True,
                verified_for_model=True,
            )
            .select_related(
                "appliance",
            )
            .prefetch_related(
                Prefetch(
                    "recipe_ingredients",
                    queryset=(
                        RecipeIngredient.objects
                        .select_related(
                            "ingredient"
                        )
                        .filter(
                            ingredient__is_seasoning=False,
                            is_optional=False,
                        )
                    ),
                    to_attr="search_ingredients",
                )
            )
        )


        # -----------------------------
        # × を付けた料理は除外
        # -----------------------------

        if request.user.is_authenticated:

            recipes = recipes.exclude(
                preferences__user=request.user,
                preferences__preference="dislike",
            )


        for recipe in recipes:

            required_items = (
                recipe.search_ingredients
            )


            required_ids = {
                item.ingredient_id
                for item in required_items
            }


            if not required_ids:
                continue


            matched_ids = (
                required_ids
                & selected_id_set
            )


            matched_count = len(
                matched_ids
            )

            required_count = len(
                required_ids
            )


            # 1個も一致しない料理は出さない
            if matched_count == 0:
                continue


            missing_ids = (
                required_ids
                - selected_id_set
            )


            match_ratio = (
                matched_count
                / required_count
            )


            # -----------------------------
            # お気に入り判定
            # -----------------------------

            is_favorite = False

            if request.user.is_authenticated:

                is_favorite = (
                    recipe.preferences
                    .filter(
                        user=request.user,
                        preference="favorite",
                    )
                    .exists()
                )


            matched_items = [
                item
                for item in required_items
                if item.ingredient_id
                in matched_ids
            ]


            missing_items = [
                item
                for item in required_items
                if item.ingredient_id
                in missing_ids
            ]


            results.append(
                {
                    "recipe": recipe,
                    "matched_count":
                        matched_count,
                    "required_count":
                        required_count,
                    "match_percent":
                        round(
                            match_ratio * 100
                        ),
                    "matched_items":
                        matched_items,
                    "missing_items":
                        missing_items,
                    "is_favorite":
                        is_favorite,
                }
            )


        # -----------------------------
        # 並び順
        #
        # 1. 一致率
        # 2. 一致食材数
        # 3. お気に入り
        # 4. スイスでの作りやすさ
        # -----------------------------

        results.sort(
            key=lambda item: (
                item["match_percent"],
                item["matched_count"],
                item["is_favorite"],
                item["recipe"].switzerland_score,
            ),
            reverse=True,
        )


    context = {
        "ingredients": ingredients,
        "selected_ids": selected_ids,
        "results": results,
        "has_search": bool(
            selected_ids
        ),
    }


    return render(
        request,
        "recipes/find_by_ingredients.html",
        context,
    )

def find_by_mood(request):

    moods = (
        MoodTag.objects
        .all()
        .order_by(
            "display_order",
            "name",
        )
    )

    selected_ids = request.GET.getlist(
        "moods"
    )

    selected_ids = [
        int(mood_id)
        for mood_id in selected_ids
        if mood_id.isdigit()
    ]

    results = []


    if selected_ids:

        selected_id_set = set(
            selected_ids
        )


        recipes = (
            Recipe.objects
            .filter(
                is_active=True,
                verified_for_model=True,
                mood_tags__id__in=selected_ids,
            )
            .select_related(
                "appliance",
            )
            .prefetch_related(
                "mood_tags",
                "recipe_ingredients__ingredient",
            )
            .distinct()
        )


        # × あまり好まないレシピは除外
        if request.user.is_authenticated:

            recipes = recipes.exclude(
                preferences__user=request.user,
                preferences__preference="dislike",
            )


        for recipe in recipes:

            recipe_moods = list(
                recipe.mood_tags.all()
            )


            matched_moods = [
                mood
                for mood in recipe_moods
                if mood.id in selected_id_set
            ]


            matched_count = len(
                matched_moods
            )


            # 選択した気分のうち
            # 何％一致したか
            match_percent = round(
                (
                    matched_count
                    / len(selected_id_set)
                )
                * 100
            )


            is_favorite = False


            if request.user.is_authenticated:

                is_favorite = (
                    recipe.preferences
                    .filter(
                        user=request.user,
                        preference="favorite",
                    )
                    .exists()
                )


            results.append(
                {
                    "recipe": recipe,
                    "matched_moods":
                        matched_moods,
                    "matched_count":
                        matched_count,
                    "match_percent":
                        match_percent,
                    "is_favorite":
                        is_favorite,
                }
            )


        results.sort(
            key=lambda item: (
                item["matched_count"],
                item["is_favorite"],
                item["recipe"].switzerland_score,
            ),
            reverse=True,
        )


    context = {
        "moods": moods,
        "selected_ids": selected_ids,
        "results": results,
        "has_search": bool(
            selected_ids
        ),
    }


    return render(
        request,
        "recipes/find_by_mood.html",
        context,
    )


def find_by_nutrition(request):

    nutrition_tags = (
        NutritionTag.objects
        .all()
        .order_by(
            "display_order",
            "name",
        )
    )

    selected_ids = request.GET.getlist(
        "nutrition"
    )

    selected_ids = [
        int(tag_id)
        for tag_id in selected_ids
        if tag_id.isdigit()
    ]

    results = []


    if selected_ids:

        selected_id_set = set(
            selected_ids
        )


        recipes = (
            Recipe.objects
            .filter(
                is_active=True,
                verified_for_model=True,
                nutrition_tags__id__in=selected_ids,
            )
            .select_related(
                "appliance",
            )
            .prefetch_related(
                "nutrition_tags",
            )
            .distinct()
        )


        if request.user.is_authenticated:

            recipes = recipes.exclude(
                preferences__user=request.user,
                preferences__preference="dislike",
            )


        for recipe in recipes:

            recipe_tags = list(
                recipe.nutrition_tags.all()
            )


            matched_tags = [
                tag
                for tag in recipe_tags
                if tag.id in selected_id_set
            ]


            matched_count = len(
                matched_tags
            )


            match_percent = round(
                (
                    matched_count
                    / len(selected_id_set)
                )
                * 100
            )


            is_favorite = False


            if request.user.is_authenticated:

                is_favorite = (
                    recipe.preferences
                    .filter(
                        user=request.user,
                        preference="favorite",
                    )
                    .exists()
                )


            results.append(
                {
                    "recipe": recipe,
                    "matched_tags":
                        matched_tags,
                    "matched_count":
                        matched_count,
                    "match_percent":
                        match_percent,
                    "is_favorite":
                        is_favorite,
                }
            )


        results.sort(
            key=lambda item: (
                item["matched_count"],
                item["is_favorite"],
                item["recipe"].switzerland_score,
            ),
            reverse=True,
        )


    context = {
        "nutrition_tags":
            nutrition_tags,
        "selected_ids":
            selected_ids,
        "results":
            results,
        "has_search":
            bool(selected_ids),
    }


    return render(
        request,
        "recipes/find_by_nutrition.html",
        context,
    )