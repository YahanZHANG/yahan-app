import random

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import (
    BooleanField,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from .models import (
    Appliance,
    Ingredient,
    MoodTag,
    NutritionTag,
    Recipe,
    RecipeHousehold,
    RecipeHouseholdInvite,
    RecipeHouseholdMembership,
    RecipeIngredient,
    RecipePreference,
    RecipeUserSettings,
)

def get_household_members(user):

    if not user.is_authenticated:
        return []

    membership = (
        RecipeHouseholdMembership.objects
        .filter(
            user=user,
        )
        .select_related(
            "household",
        )
        .first()
    )

    if membership is None:

        return [
            user
        ]

    return [
        member.user
        for member
        in (
            membership.household
            .members
            .select_related(
                "user"
            )
            .order_by(
                "id"
            )
        )
    ]


def with_effective_make_ahead(
    queryset,
    user,
):

    if not user.is_authenticated:

        return queryset.annotate(
            effective_make_ahead=F(
                "is_make_ahead"
            )
        )

    override_query = (
        RecipePreference.objects
        .filter(
            user=user,
            recipe=OuterRef("pk"),
        )
        .values(
            "make_ahead_override"
        )[:1]
    )

    return queryset.annotate(
        effective_make_ahead=Coalesce(
            Subquery(
                override_query,
                output_field=BooleanField(),
            ),
            F(
                "is_make_ahead"
            ),
            output_field=BooleanField(),
        )
    )


def with_my_rating(
    queryset,
    user,
):

    if not user.is_authenticated:

        return queryset.annotate(
            my_rating=Value(
                None,
                output_field=IntegerField(),
            )
        )

    rating_query = (
        RecipePreference.objects
        .filter(
            user=user,
            recipe=OuterRef("pk"),
        )
        .values(
            "rating"
        )[:1]
    )

    return queryset.annotate(
        my_rating=Subquery(
            rating_query,
            output_field=IntegerField(),
        )
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

    recipes = with_effective_make_ahead(
        recipes,
        request.user,
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
    # 作りおき
    # =====================================

    if make_ahead:

        recipes = recipes.filter(
            effective_make_ahead=True,
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


    preference_obj = None
    current_rating = None


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

        current_rating = (
            preference_obj.rating
        )


    if (
        preference_obj
        and preference_obj.make_ahead_override
        is not None
    ):

        effective_make_ahead = (
            preference_obj.make_ahead_override
        )

    else:

        effective_make_ahead = (
            recipe.is_make_ahead
        )


    family_ratings = []


    if request.user.is_authenticated:

        family_members = (
            get_household_members(
                request.user
            )
        )

        family_user_ids = [
            member.id
            for member in family_members
        ]


        rating_map = {
            item.user_id: item.rating
            for item in (
                RecipePreference.objects
                .filter(
                    recipe=recipe,
                    user_id__in=family_user_ids,
                    rating__isnull=False,
                )
            )
        }


        for member in family_members:

            rating = rating_map.get(
                member.id
            )

            family_ratings.append(
                {
                    "username":
                        member.username,

                    "rating":
                        rating,

                    "stars":
                        (
                            "★" * rating
                            + "☆" * (
                                5 - rating
                            )
                        )
                        if rating
                        else "未評価",
                }
            )


    context = {
        "recipe":
            recipe,

        "food_ingredients":
            food_ingredients,

        "seasonings":
            seasonings,

        "current_rating":
            current_rating,

    "rating_choices":
        [1, 2, 3, 4, 5],

    "effective_make_ahead":
        effective_make_ahead,

    "family_ratings":
        family_ratings,
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

    rated_recipes = (
        Recipe.objects
        .filter(
            preferences__user=request.user,
            preferences__rating__isnull=False,
            is_active=True,
            verified_for_model=True,
        )
        .annotate(
            my_rating=F(
                "preferences__rating"
            )
        )
        .select_related(
            "appliance"
        )
        .distinct()
    )


    high_to_low = (
        rated_recipes
        .order_by(
            "-my_rating",
            "name",
        )
    )


    low_to_high = (
        rated_recipes
        .order_by(
            "my_rating",
            "name",
        )
    )


    context = {
        "high_to_low":
            high_to_low,

        "low_to_high":
            low_to_high,
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

def calculate_random_weight(
    ratings,
):

    if not ratings:
        return 4.0


    average = (
        sum(ratings)
        / len(ratings)
    )


    if average < 1.5:
        weight = 0.5

    elif average < 2.5:
        weight = 1.5

    elif average < 3.5:
        weight = 3.5

    elif average < 4.5:
        weight = 6.5

    else:
        weight = 10.0


    if len(ratings) >= 2:

        # 家族全員かなり好き
        if min(ratings) >= 4:

            weight += 5.0


        # 好みが大きく割れている
        elif (
            max(ratings)
            - min(ratings)
            >= 3
        ):

            weight *= 0.5


    return max(
        weight,
        0.25,
    )


def random_recipe(request):

    recipes = list(
        Recipe.objects
        .filter(
            is_active=True,
            verified_for_model=True,
        )
        .select_related(
            "appliance",
        )
        .prefetch_related(
            "mood_tags",
            "nutrition_tags",
            "recipe_ingredients__ingredient",
        )
    )


    recipe = None


    if recipes:

        if request.user.is_authenticated:

            family_members = (
                get_household_members(
                    request.user
                )
            )

            family_user_ids = [
                member.id
                for member
                in family_members
            ]


            recipe_ids = [
                item.id
                for item
                in recipes
            ]


            rating_map = {
                recipe_id: []
                for recipe_id
                in recipe_ids
            }


            preferences = (
                RecipePreference.objects
                .filter(
                    recipe_id__in=
                        recipe_ids,

                    user_id__in=
                        family_user_ids,

                    rating__isnull=False,
                )
                .values(
                    "recipe_id",
                    "rating",
                )
            )


            for item in preferences:

                rating_map[
                    item[
                        "recipe_id"
                    ]
                ].append(
                    item[
                        "rating"
                    ]
                )


            weights = [
                calculate_random_weight(
                    rating_map[
                        item.id
                    ]
                )
                for item
                in recipes
            ]


            recipe = random.choices(
                recipes,
                weights=weights,
                k=1,
            )[0]


        else:

            recipe = random.choice(
                recipes
            )


    return render(
        request,
        "recipes/random_recipe.html",
        {
            "recipe":
                recipe,
        },
    )

@login_required
@require_POST
def set_rating(request, pk):

    recipe = get_object_or_404(
        Recipe,
        pk=pk,
        is_active=True,
        verified_for_model=True,
    )

    raw_rating = request.POST.get(
        "rating",
        "",
    )

    preference, _ = (
        RecipePreference.objects
        .get_or_create(
            user=request.user,
            recipe=recipe,
        )
    )


    # 評価をなくす
    if raw_rating == "":

        preference.rating = None

        preference.save(
            update_fields=[
                "rating",
            ]
        )

        return redirect(
            "recipes:detail",
            pk=recipe.pk,
        )


    if (
        not raw_rating.isdigit()
        or int(raw_rating) not in range(1, 6)
    ):

        return redirect(
            "recipes:detail",
            pk=recipe.pk,
        )


    rating = int(
        raw_rating
    )


    # 同じ評価を押した場合も解除
    if preference.rating == rating:

        preference.rating = None

    else:

        preference.rating = rating


    preference.save(
        update_fields=[
            "rating",
        ]
    )


    return redirect(
        "recipes:detail",
        pk=recipe.pk,
    )

@login_required
@require_POST
def toggle_make_ahead(request, pk):

    recipe = get_object_or_404(
        Recipe,
        pk=pk,
        is_active=True,
        verified_for_model=True,
    )

    preference, _ = (
        RecipePreference.objects
        .get_or_create(
            user=request.user,
            recipe=recipe,
        )
    )

    if (
        preference.make_ahead_override
        is None
    ):

        current_value = (
            recipe.is_make_ahead
        )

    else:

        current_value = (
            preference.make_ahead_override
        )

    preference.make_ahead_override = (
        not current_value
    )

    preference.save(
        update_fields=[
            "make_ahead_override",
        ]
    )

    return redirect(
        "recipes:detail",
        pk=recipe.pk,
    )

@login_required
def settings_page(request):

    membership = (
        RecipeHouseholdMembership.objects
        .filter(
            user=request.user,
        )
        .select_related(
            "household",
        )
        .first()
    )

    members = []

    pending_sent_invites = []

    if membership:

        members = (
            membership.household
            .members
            .select_related(
                "user",
            )
            .order_by(
                "id",
            )
        )

        pending_sent_invites = (
            membership.household
            .invites
            .filter(
                status="pending",
            )
            .select_related(
                "invited_user",
            )
            .order_by(
                "-created_at",
            )
        )


    received_invites = (
        RecipeHouseholdInvite.objects
        .filter(
            invited_user=request.user,
            status="pending",
        )
        .select_related(
            "invited_by",
        )
        .order_by(
            "-created_at",
        )
    )


    user_settings, _ = (
        RecipeUserSettings.objects
        .get_or_create(
            user=request.user,
        )
    )


    context = {
        "membership":
            membership,

        "members":
            members,

        "pending_sent_invites":
            pending_sent_invites,

        "received_invites":
            received_invites,

        "recipe_user_settings":
            user_settings,
    }


    return render(
        request,
        "recipes/settings.html",
        context,
    )


@login_required
@require_POST
def invite_family_member(request):

    username = (
        request.POST.get(
            "username",
            "",
        )
        .strip()
    )

    User = get_user_model()


    invited_user = (
        User.objects
        .filter(
            username__iexact=username,
        )
        .first()
    )


    if invited_user is None:

        messages.error(
            request,
            "そのユーザー名は見つからなかった。",
        )

        return redirect(
            "recipes:settings",
        )


    if invited_user == request.user:

        messages.error(
            request,
            "自分自身は招待できない。",
        )

        return redirect(
            "recipes:settings",
        )


    membership = (
        RecipeHouseholdMembership.objects
        .filter(
            user=request.user,
        )
        .select_related(
            "household",
        )
        .first()
    )


    # 初めて招待するとき家族を自動作成
    if membership is None:

        household = (
            RecipeHousehold.objects
            .create(
                created_by=request.user,
            )
        )

        membership = (
            RecipeHouseholdMembership.objects
            .create(
                household=household,
                user=request.user,
            )
        )

    else:

        household = (
            membership.household
        )


    existing_membership = (
        RecipeHouseholdMembership.objects
        .filter(
            user=invited_user,
        )
        .select_related(
            "household",
        )
        .first()
    )


    if existing_membership:

        if (
            existing_membership.household_id
            == household.id
        ):

            messages.error(
                request,
                "そのユーザーはすでに家族メンバーです。",
            )

        else:

            messages.error(
                request,
                "そのユーザーはすでに別の家族に参加しています。",
            )

        return redirect(
            "recipes:settings",
        )


    if (
        RecipeHouseholdInvite.objects
        .filter(
            household=household,
            invited_user=invited_user,
            status="pending",
        )
        .exists()
    ):

        messages.error(
            request,
            "そのユーザーはすでに招待中です。",
        )

        return redirect(
            "recipes:settings",
        )


    RecipeHouseholdInvite.objects.create(
        household=household,
        invited_by=request.user,
        invited_user=invited_user,
    )


    messages.success(
        request,
        f"{invited_user.username} を招待しました。",
    )


    return redirect(
        "recipes:settings",
    )


@login_required
@require_POST
@transaction.atomic
def respond_family_invite(
    request,
    invite_id,
):

    invite = get_object_or_404(
        RecipeHouseholdInvite.objects
        .select_related(
            "household",
        ),
        pk=invite_id,
        invited_user=request.user,
        status="pending",
    )


    action = request.POST.get(
        "action"
    )


    if action == "accept":

        if (
            RecipeHouseholdMembership.objects
            .filter(
                user=request.user,
            )
            .exists()
        ):

            messages.error(
                request,
                "すでに別の家族に参加しています。",
            )

            return redirect(
                "recipes:settings",
            )


        RecipeHouseholdMembership.objects.create(
            household=invite.household,
            user=request.user,
        )

        invite.status = "accepted"

        invite.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


        # 他の招待は自動的に辞退
        RecipeHouseholdInvite.objects.filter(
            invited_user=request.user,
            status="pending",
        ).exclude(
            pk=invite.pk,
        ).update(
            status="declined",
        )


        messages.success(
            request,
            "家族に参加しました。",
        )


    elif action == "decline":

        invite.status = "declined"

        invite.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


    return redirect(
        "recipes:settings",
    )


@login_required
@require_POST
def set_font_size(request):

    font_size = request.POST.get(
        "font_size"
    )

    if font_size not in {
        "small",
        "medium",
        "large",
    }:

        return redirect(
            "recipes:settings",
        )


    RecipeUserSettings.objects.update_or_create(
        user=request.user,
        defaults={
            "font_size":
                font_size,
        },
    )


    return redirect(
        "recipes:settings",
    )


