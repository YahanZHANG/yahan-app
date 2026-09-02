import random

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .constants import (
    MOOD_TAGS,
    NUTRITION_TAGS,
)

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
    return render(
        request,
        "recipes/home.html",
    )


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
    )


    # =====================================
    # 検索条件
    # =====================================

    query = request.GET.get(
        "q",
        "",
    ).strip()

    cooking_mode = request.GET.get(
        "mode",
        "",
    )

    category = request.GET.get(
        "category",
        "",
    )

    make_ahead = (
        request.GET.get("make_ahead")
        == "1"
    )


    # =====================================
    # 料理名検索
    # =====================================

    if query:

        recipes = recipes.filter(
            name__icontains=query,
        )


    # =====================================
    # 自動 / 手動
    # =====================================

    if cooking_mode in {
        "auto",
        "manual",
    }:

        recipes = recipes.filter(
            cooking_mode=cooking_mode,
        )


    # =====================================
    # カテゴリー
    # =====================================

    valid_categories = {
        choice[0]
        for choice
        in Recipe.CATEGORY_CHOICES
    }

    if category in valid_categories:

        recipes = recipes.filter(
            category=category,
        )


    # =====================================
    # 作りおき向き
    # =====================================

    if make_ahead:

        recipes = recipes.filter(
            is_make_ahead=True,
        )


    recipes = recipes.order_by(
        "name"
    )


    context = {
        "appliance": appliance,
        "recipes": recipes,

        "query": query,
        "selected_mode": cooking_mode,
        "selected_category": category,
        "make_ahead": make_ahead,

        "category_choices":
            Recipe.CATEGORY_CHOICES,
    }

    return render(
        request,
        "recipes/recipe_list.html",
        context,
    )


def recipe_detail(request, pk):

    recipe = get_object_or_404(
        Recipe.objects
        .select_related(
            "appliance"
        )
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

    for item in (
        recipe.recipe_ingredients.all()
    ):

        if item.is_seasoning:
            seasonings.append(
                item
            )

        else:
            food_ingredients.append(
                item
            )


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

            preference = (
                preference_obj.preference
            )


    context = {
        "recipe": recipe,
        "food_ingredients":
            food_ingredients,
        "seasonings":
            seasonings,
        "preference":
            preference,
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

    preference = (
        request.POST.get(
            "preference"
        )
    )


    if preference not in {
        "favorite",
        "dislike",
    }:

        return JsonResponse(
            {
                "ok": False,
                "error":
                    "invalid preference",
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


    # =====================================
    # 同じボタンをもう一度押した場合は解除
    # =====================================

    if (
        existing
        and
        existing.preference
        == preference
    ):

        existing.delete()

        return JsonResponse(
            {
                "ok": True,
                "preference": None,
            }
        )


    # =====================================
    # ★ → ×、または × → ★ の場合は状態変更
    # =====================================

    RecipePreference.objects.update_or_create(
        user=request.user,
        recipe=recipe,
        defaults={
            "preference":
                preference,
        },
    )

    return JsonResponse(
        {
            "ok": True,
            "preference":
                preference,
        }
    )


@login_required
def my_recipes(request):

    favorites = (
        Recipe.objects
        .filter(
            preferences__user=
                request.user,
            preferences__preference=
                "favorite",
            is_active=True,
            verified_for_model=True,
        )
        .select_related(
            "appliance"
        )
        .prefetch_related(
            "recipe_ingredients__ingredient",
        )
        .order_by(
            "name"
        )
    )


    dislikes = (
        Recipe.objects
        .filter(
            preferences__user=
                request.user,
            preferences__preference=
                "dislike",
            is_active=True,
            verified_for_model=True,
        )
        .select_related(
            "appliance"
        )
        .prefetch_related(
            "recipe_ingredients__ingredient",
        )
        .order_by(
            "name"
        )
    )


    context = {
        "favorites":
            favorites,
        "dislikes":
            dislikes,
    }

    return render(
        request,
        "recipes/my_recipes.html",
        context,
    )


def find_by_ingredients(request):

    # =====================================
    # ユーザーが選択する食材グループ
    # =====================================

    ingredient_queryset = (
        Ingredient.objects
        .filter(
            recipe_ingredients__is_seasoning=False,
        )
        .distinct()
        .order_by(
            "category",
            "name",
        )
    )


    # =====================================
    # 同じ search_group を1回だけ表示
    # =====================================

    option_map = {}


    for ingredient in (
        ingredient_queryset
    ):

        group_name = (
            ingredient.search_group
            or ingredient.name
        )


        if (
            group_name
            not in option_map
        ):

            option_map[
                group_name
            ] = {
                "name":
                    group_name,

                "category":
                    ingredient.category,

                "category_label":
                    ingredient
                    .get_category_display(),
            }


    search_options = sorted(
        option_map.values(),
        key=lambda item: (
            item[
                "category_label"
            ],
            item[
                "name"
            ],
        ),
    )


    # =====================================
    # GETで選択されたグループ
    # =====================================

    selected_groups = (
        request.GET.getlist(
            "groups"
        )
    )


    selected_group_set = set(
        selected_groups
    )


    results = []


    if selected_groups:

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
                        RecipeIngredient
                        .objects
                        .select_related(
                            "ingredient"
                        )
                        .filter(
                            is_seasoning=False,
                            is_optional=False,
                        )
                    ),
                    to_attr=
                        "search_ingredients",
                )
            )
        )


        # =====================================
        # × あまり好まない料理を除外
        # =====================================

        if (
            request.user
            .is_authenticated
        ):

            recipes = (
                recipes.exclude(
                    preferences__user=
                        request.user,
                    preferences__preference=
                        "dislike",
                )
            )


        for recipe in recipes:

            required_items = (
                recipe
                .search_ingredients
            )


            # =====================================
            # レシピに必要な検索グループ
            # =====================================

            required_groups = {
                (
                    item.ingredient
                    .search_group
                    or
                    item.ingredient.name
                )
                for item
                in required_items
            }


            if not required_groups:

                continue


            matched_groups = (
                required_groups
                &
                selected_group_set
            )


            if not matched_groups:

                continue


            missing_groups = (
                required_groups
                -
                selected_group_set
            )


            matched_count = len(
                matched_groups
            )

            required_count = len(
                required_groups
            )


            match_ratio = (
                matched_count
                /
                required_count
            )


            # =====================================
            # お気に入り判定
            # =====================================

            is_favorite = False


            if (
                request.user
                .is_authenticated
            ):

                is_favorite = (
                    recipe.preferences
                    .filter(
                        user=
                            request.user,
                        preference=
                            "favorite",
                    )
                    .exists()
                )


            # =====================================
            # 実際のレシピ食材を表示
            # =====================================

            matched_items = [
                item
                for item
                in required_items
                if (
                    item.ingredient
                    .search_group
                    or
                    item.ingredient.name
                )
                in matched_groups
            ]


            missing_items = [
                item
                for item
                in required_items
                if (
                    item.ingredient
                    .search_group
                    or
                    item.ingredient.name
                )
                in missing_groups
            ]


            results.append(
                {
                    "recipe":
                        recipe,

                    "matched_count":
                        matched_count,

                    "required_count":
                        required_count,

                    "match_percent":
                        round(
                            match_ratio
                            * 100
                        ),

                    "matched_items":
                        matched_items,

                    "missing_items":
                        missing_items,

                    "is_favorite":
                        is_favorite,
                }
            )


        # =====================================
        # おすすめ順
        # =====================================

        results.sort(
            key=lambda item: (
                item[
                    "match_percent"
                ],
                item[
                    "matched_count"
                ],
                item[
                    "is_favorite"
                ],
                item[
                    "recipe"
                ].switzerland_score,
            ),
            reverse=True,
        )


    context = {
        "search_options":
            search_options,

        "selected_groups":
            selected_groups,

        "results":
            results,

        "has_search":
            bool(
                selected_groups
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
        .filter(
            name__in=
                MOOD_TAGS.keys(),
        )
        .order_by(
            "display_order",
            "name",
        )
    )


    selected_ids = (
        request.GET.getlist(
            "moods"
        )
    )


    selected_ids = [
        int(
            mood_id
        )
        for mood_id
        in selected_ids
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
                mood_tags__id__in=
                    selected_ids,
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


        # =====================================
        # × あまり好まないレシピは除外
        # =====================================

        if (
            request.user
            .is_authenticated
        ):

            recipes = (
                recipes.exclude(
                    preferences__user=
                        request.user,
                    preferences__preference=
                        "dislike",
                )
            )


        for recipe in recipes:

            recipe_moods = list(
                recipe
                .mood_tags
                .all()
            )


            matched_moods = [
                mood
                for mood
                in recipe_moods
                if mood.id
                in selected_id_set
            ]


            matched_count = len(
                matched_moods
            )


            # 選択した気分のうち
            # 何％一致したか
            match_percent = round(
                (
                    matched_count
                    /
                    len(
                        selected_id_set
                    )
                )
                * 100
            )


            is_favorite = False


            if (
                request.user
                .is_authenticated
            ):

                is_favorite = (
                    recipe.preferences
                    .filter(
                        user=
                            request.user,
                        preference=
                            "favorite",
                    )
                    .exists()
                )


            results.append(
                {
                    "recipe":
                        recipe,

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
                item[
                    "matched_count"
                ],
                item[
                    "is_favorite"
                ],
                item[
                    "recipe"
                ].switzerland_score,
            ),
            reverse=True,
        )


    context = {
        "moods":
            moods,

        "selected_ids":
            selected_ids,

        "results":
            results,

        "has_search":
            bool(
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
        .filter(
            name__in=
                NUTRITION_TAGS.keys(),
        )
        .order_by(
            "display_order",
            "name",
        )
    )


    selected_ids = (
        request.GET.getlist(
            "nutrition"
        )
    )


    selected_ids = [
        int(
            tag_id
        )
        for tag_id
        in selected_ids
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
                nutrition_tags__id__in=
                    selected_ids,
            )
            .select_related(
                "appliance",
            )
            .prefetch_related(
                "nutrition_tags",
            )
            .distinct()
        )


        if (
            request.user
            .is_authenticated
        ):

            recipes = (
                recipes.exclude(
                    preferences__user=
                        request.user,
                    preferences__preference=
                        "dislike",
                )
            )


        for recipe in recipes:

            recipe_tags = list(
                recipe
                .nutrition_tags
                .all()
            )


            matched_tags = [
                tag
                for tag
                in recipe_tags
                if tag.id
                in selected_id_set
            ]


            matched_count = len(
                matched_tags
            )


            match_percent = round(
                (
                    matched_count
                    /
                    len(
                        selected_id_set
                    )
                )
                * 100
            )


            is_favorite = False


            if (
                request.user
                .is_authenticated
            ):

                is_favorite = (
                    recipe.preferences
                    .filter(
                        user=
                            request.user,
                        preference=
                            "favorite",
                    )
                    .exists()
                )


            results.append(
                {
                    "recipe":
                        recipe,

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
                item[
                    "matched_count"
                ],
                item[
                    "is_favorite"
                ],
                item[
                    "recipe"
                ].switzerland_score,
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
            bool(
                selected_ids
            ),
    }


    return render(
        request,
        "recipes/find_by_nutrition.html",
        context,
    )


def random_recipe(request):

    recipes = (
        Recipe.objects
        .filter(
            is_active=True,
            verified_for_model=True,
        )
        .select_related(
            "appliance",
        )
    )


    # =====================================
    # × あまり好まないレシピを除外
    # =====================================

    if (
        request.user
        .is_authenticated
    ):

        recipes = recipes.exclude(
            preferences__user=
                request.user,
            preferences__preference=
                "dislike",
        )


    recipe_ids = list(
        recipes.values_list(
            "id",
            flat=True,
        )
    )


    recipe = None


    if recipe_ids:

        recipe_id = random.choice(
            recipe_ids
        )


        recipe = (
            Recipe.objects
            .select_related(
                "appliance",
            )
            .prefetch_related(
                "mood_tags",
                "nutrition_tags",
                "recipe_ingredients__ingredient",
            )
            .get(
                pk=recipe_id
            )
        )


    return render(
        request,
        "recipes/random_recipe.html",
        {
            "recipe":
                recipe,
        },
    )