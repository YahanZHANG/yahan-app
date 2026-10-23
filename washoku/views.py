import json
import random

from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .alerts import send_admin_alert
from .photos import delete_uploaded_photos, upload_photo
from .push import send_reply_push, send_stamp_push
from .forms import (
    CommentEditForm,
    CommentForm,
    FeedbackForm,
    PostForm,
    RecipeSubmissionForm,
    SubstituteForm,
)
from .models import (
    Announcement,
    Comment,
    CommentReaction,
    CommentReport,
    Feedback,
    Household,
    HouseholdInvite,
    HouseholdMember,
    Ingredient,
    MemberPhoto,
    MoodTag,
    Notification,
    Post,
    PostReaction,
    PushSubscription,
    Recipe,
    RecipeFavorite,
    RecipeIngredient,
    RecipeNote,
    RecipeRating,
    ShopType,
    Store,
    Substitute,
    REACTION_CHOICES,
    REACTION_EMOJI,
)


# 同じ人が続けてコメントできるまでの間隔
COMMENT_INTERVAL = timedelta(seconds=60)

# 質問箱を続けて送れるまでの間隔 (秒)
FEEDBACK_INTERVAL_SECONDS = 60

# 確認待ちのまま置いておける投稿レシピ・コラム・商品の数 (1人あたり、種類ごと)
MAX_PENDING_SUBMISSIONS = 5


# =========================================================
# 共通
# =========================================================

def visible_recipes(user):
    """
    一般の人には公開中のレシピだけ。管理者には下書きも見せる (確認用)。
    """

    recipes = Recipe.objects.all()

    if not user.is_staff:
        recipes = recipes.filter(status="published")

    return recipes


def family_members(user):
    """
    家族のメンバー (自分を含む)。家族に入っていなければ自分だけ。
    """

    if not user.is_authenticated:
        return []

    membership = (
        HouseholdMember.objects
        .filter(user=user)
        .select_related("household")
        .first()
    )

    if membership is None:
        return [user]

    return [
        member.user
        for member in membership.household.members.select_related("user")
    ]


def family_ratings(user, recipe_ids):
    """
    {recipe_id: [家族の評価, ...]}
    """

    ratings = defaultdict(list)

    members = family_members(user)

    if not members:
        return ratings

    for recipe_id, rating in RecipeRating.objects.filter(
        user__in=members,
        recipe_id__in=recipe_ids,
    ).values_list("recipe_id", "rating"):
        ratings[recipe_id].append(rating)

    return ratings


def attach_family_rating(recipes, user):
    """
    各レシピに family_average (家族の平均評価) を付ける。
    """

    recipes = list(recipes)

    ratings = family_ratings(user, [recipe.pk for recipe in recipes])

    for recipe in recipes:

        values = ratings.get(recipe.pk, [])

        recipe.family_average = (
            round(sum(values) / len(values), 1)
            if values else None
        )

    return recipes


def shop_choices():
    return list(ShopType.objects.all())


def recipe_card_queryset(queryset):
    return queryset.prefetch_related("mood_tags").annotate(
        comment_count=Count(
            "comments",
            filter=Q(comments__is_hidden=False, comments__is_deleted=False),
            distinct=True,
        )
    )


def public_comment_targets():
    """
    公開中のレシピ・投稿か、食材・お店に付いたコメントだけを選ぶ条件。
    """

    return (
        (Q(recipe__isnull=True) | Q(recipe__status="published"))
        & (Q(post__isnull=True) | Q(post__status="published"))
    )


def questions_with_answer_state():
    """
    公開中の質問に、返信があるか (has_answer) と返信の数 (answer_count) を付ける。
    """

    answers = Comment.objects.filter(
        parent=OuterRef("pk"),
        is_hidden=False,
        is_deleted=False,
    )

    return (
        Comment.objects
        .filter(
            parent__isnull=True,
            kind="question",
            is_hidden=False,
            is_deleted=False,
        )
        .filter(public_comment_targets())
        .annotate(
            has_answer=Exists(answers),
            answer_count=Count(
                "replies",
                filter=Q(replies__is_hidden=False, replies__is_deleted=False),
                distinct=True,
            ),
        )
        .select_related("recipe", "ingredient", "store", "post", "author")
        .order_by("-created_at")
    )


def open_questions():
    """
    返信がまだない質問 (新しい順)。
    """

    return questions_with_answer_state().filter(has_answer=False)


# =========================================================
# ホーム
# =========================================================

def latest_columns(exclude=None, limit=3):
    """
    新しいコラム。HOME と、コラムの下の「ほかのコラム」に出す。
    """

    columns = Post.objects.filter(kind="column", status="published").select_related("author")

    if exclude:
        columns = columns.exclude(pk=exclude.pk)

    return columns[:limit]


def home(request):

    recipes = visible_recipes(request.user)

    return render(
        request,
        "washoku/home.html",
        {
            "latest_activity": activity_entries(comment_limit=5, post_limit=5)[:5],
            "questions": open_questions()[:3],
            "columns": latest_columns(),
            "announcements": list(Announcement.current()),
            "moods": MoodTag.objects.all(),
            "categories": Recipe.CATEGORY_CHOICES[:-1],
            "recipe_count": recipes.count(),
        },
    )


# =========================================================
# 一覧・検索
# =========================================================

# 栄養で絞り込む条件 (1人分)
NUTRITION_FILTERS = [
    ("light", "400kcal以下", Q(energy_kcal__lte=400)),
    ("protein", "たんぱく質20g以上", Q(protein_g__gte=20)),
    ("lowfat", "脂質15g以下", Q(fat_g__lte=15)),
    ("lowcarb", "炭水化物30g以下", Q(carbs_g__lte=30)),
    ("lowsalt", "塩分2g以下", Q(salt_g__lte=2)),
]

SORT_CHOICES = [
    ("name", "名前順"),
    ("new", "新しい順"),
    ("time", "早くできる順"),
    ("light", "カロリー控えめ順"),
    ("family", "家族の評価順"),
]


def recipe_list(request):

    recipes = visible_recipes(request.user)

    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    mood = request.GET.get("mood", "")
    max_time = request.GET.get("time", "")
    shop = request.GET.get("shop", "")
    sort = request.GET.get("sort", "name")
    nutrition = [
        value for value in request.GET.getlist("n")
        if value in {key for key, _label, _q in NUTRITION_FILTERS}
    ]

    if query:
        recipes = recipes.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(ingredients__name__icontains=query)
            | Q(ingredients__search_group__icontains=query)
        ).distinct()

    if category:
        recipes = recipes.filter(category=category)

    if mood:
        recipes = recipes.filter(mood_tags__pk=mood)

    if max_time.isdigit():
        recipes = recipes.filter(cooking_time_minutes__lte=int(max_time))

    if shop.isdigit():
        recipes = recipes.filter(shop_rank__lte=int(shop))

    for key, _label, condition in NUTRITION_FILTERS:
        if key in nutrition:
            recipes = recipes.filter(condition)

    if sort == "new":
        recipes = recipes.order_by("-created_at")
    elif sort == "time":
        recipes = recipes.order_by("cooking_time_minutes", "name")
    elif sort == "light":
        recipes = recipes.order_by(F("energy_kcal").asc(nulls_last=True), "name")
    else:
        recipes = recipes.order_by("name")

    recipes = attach_family_rating(
        recipe_card_queryset(recipes),
        request.user,
    )

    if sort == "family":
        recipes.sort(
            key=lambda recipe: (
                recipe.family_average is None,
                -(recipe.family_average or 0),
                recipe.name,
            )
        )

    return render(
        request,
        "washoku/recipe_list.html",
        {
            "recipes": recipes,
            "query": query,
            "category": category,
            "mood": mood,
            "max_time": max_time,
            "shop": shop,
            "sort": sort,
            "categories": Recipe.CATEGORY_CHOICES[:-1],
            "moods": MoodTag.objects.all(),
            "shops": shop_choices(),
            "sort_choices": SORT_CHOICES,
            "nutrition": nutrition,
            "time_choices": [(15, "15分以内"), (30, "30分以内"), (60, "1時間以内")],
        },
    )


# 栄養で選ぶ: (GET の名前, 見出し, 項目, 以上/以下, 選べる値)
NUTRITION_LIMITS = [
    ("kcal", "カロリー", "energy_kcal", "lte", [300, 400, 500, 600, 700], "kcal以下"),
    ("protein", "たんぱく質", "protein_g", "gte", [15, 20, 25, 30], "g以上"),
    ("fat", "脂質", "fat_g", "lte", [10, 15, 20, 30], "g以下"),
    ("carbs", "炭水化物", "carbs_g", "lte", [20, 30, 50, 70], "g以下"),
    ("salt", "塩分", "salt_g", "lte", [1.5, 2, 2.5, 3], "g以下"),
]

NUTRITION_SORTS = [
    ("kcal", "カロリーが低い順", F("energy_kcal").asc(nulls_last=True)),
    ("protein", "たんぱく質が多い順", F("protein_g").desc(nulls_last=True)),
    ("fat", "脂質が少ない順", F("fat_g").asc(nulls_last=True)),
    ("carbs", "炭水化物が少ない順", F("carbs_g").asc(nulls_last=True)),
    ("salt", "塩分が少ない順", F("salt_g").asc(nulls_last=True)),
]

# よく使う組み合わせ (押すと上の条件に入る)
NUTRITION_PRESETS = [
    ("軽めにしたい", "kcal=400&sort=kcal"),
    ("たんぱく質をとりたい", "protein=20&sort=protein"),
    ("塩分控えめ", "salt=2&sort=salt"),
    ("糖質控えめ", "carbs=30&sort=carbs"),
    ("脂質控えめ", "fat=15&sort=fat"),
]


def find_by_nutrition(request):
    """
    1人分の栄養の目安 (カロリー・PFC・塩分) の条件と並び順で、レシピを探す。
    栄養の目安がないレシピは出さない。
    """

    recipes = visible_recipes(request.user).filter(energy_kcal__isnull=False)

    limits = []
    selected = {}

    for key, label, field, lookup, values, unit in NUTRITION_LIMITS:

        raw = request.GET.get(key, "")
        value = next((item for item in values if str(item) == raw), None)

        if value is not None:
            recipes = recipes.filter(**{f"{field}__{lookup}": value})
            selected[key] = raw

        limits.append(
            {
                "key": key,
                "label": label,
                "options": [(str(item), f"{item}{unit}") for item in values],
                "value": raw if value is not None else "",
            }
        )

    category = request.GET.get("category", "")

    if category in dict(Recipe.CATEGORY_CHOICES):
        recipes = recipes.filter(category=category)
    else:
        category = ""

    sorts = {key: order for key, _label, order in NUTRITION_SORTS}
    sort = request.GET.get("sort", "kcal")

    if sort not in sorts:
        sort = "kcal"

    recipes = attach_family_rating(
        recipe_card_queryset(recipes.order_by(sorts[sort], "name")),
        request.user,
    )

    return render(
        request,
        "washoku/find_by_nutrition.html",
        {
            "recipes": recipes,
            "limits": limits,
            "has_condition": bool(selected or category),
            "category": category,
            "categories": Recipe.CATEGORY_CHOICES[:-1],
            "sort": sort,
            "sort_choices": [(key, label) for key, label, _order in NUTRITION_SORTS],
            "presets": NUTRITION_PRESETS,
        },
    )


def find_by_mood(request):

    moods = MoodTag.objects.annotate(
        recipe_count=Count(
            "recipes",
            filter=(
                Q(recipes__status="published")
                if not request.user.is_staff else Q()
            ),
        )
    )

    return render(
        request,
        "washoku/find_by_mood.html",
        {
            "moods": moods,
        },
    )


def find_by_ingredients(request):
    """
    家にある食材を選ぶと、足りない材料が少ない順にレシピを出す。
    調味料と「なくてもよい」材料は数えない。
    「必ず使う」にした食材 (賞味期限が近いものなど) は、
    それを全部使うレシピだけに絞る。
    """

    groups = (
        Ingredient.objects
        .filter(recipe_ingredients__is_seasoning=False)
        .exclude(category="seasoning")
        .distinct()
    )

    category_order = [value for value, _label in Ingredient.CATEGORY_CHOICES]

    options = {}

    for ingredient in groups:
        options.setdefault(ingredient.group_name, ingredient)

    options_by_category = defaultdict(list)

    for name, ingredient in sorted(
        options.items(),
        key=lambda item: (category_order.index(item[1].category), item[0]),
    ):
        options_by_category[ingredient.get_category_display()].append(name)

    must_set = set(request.GET.getlist("m"))

    # 「必ず使う」にした食材は「家にある」にも入れる
    selected_set = set(request.GET.getlist("g")) | must_set

    results = []

    if selected_set:

        items = RecipeIngredient.objects.filter(
            is_seasoning=False,
        ).select_related("ingredient")

        recipes = visible_recipes(request.user).prefetch_related(
            Prefetch("recipe_ingredients", queryset=items, to_attr="all_items")
        )

        for recipe in recipes:

            recipe.main_items = [
                item for item in recipe.all_items
                if not item.is_optional
            ]

            # 必ず使う食材は「なくてもよい」材料として入っていても使えるので数える
            used = {item.ingredient.group_name for item in recipe.all_items}

            if not must_set <= used:
                continue

            names = [item.ingredient.group_name for item in recipe.main_items]

            have = [name for name in names if name in selected_set]

            if not have and not must_set:
                continue

            missing = [
                item.ingredient.name
                for item in recipe.main_items
                if item.ingredient.group_name not in selected_set
            ]

            results.append(
                {
                    "recipe": recipe,
                    "have": have,
                    "missing": missing,
                    "uses": sorted(must_set),
                }
            )

        results.sort(
            key=lambda result: (
                len(result["missing"]),
                -len(result["have"]),
                result["recipe"].name,
            )
        )

    return render(
        request,
        "washoku/find_by_ingredients.html",
        {
            "options_by_category": dict(options_by_category),
            "selected": selected_set,
            "must": must_set,
            "results": results[:30],
            "searched": bool(selected_set),
        },
    )


def random_weight(ratings):
    """
    家族の評価が高いほど出やすくする。評価がなければ普通。
    """

    if not ratings:
        return 4.0

    average = sum(ratings) / len(ratings)

    return max(average ** 2, 0.5)


def random_recipe(request):

    recipes = visible_recipes(request.user)

    mood = request.GET.get("mood", "")
    shop = request.GET.get("shop", "")

    if mood.isdigit():
        recipes = recipes.filter(mood_tags__pk=mood)

    if shop.isdigit():
        recipes = recipes.filter(shop_rank__lte=int(shop))

    recipes = list(recipes.prefetch_related("mood_tags"))

    ratings = family_ratings(
        request.user,
        [recipe.pk for recipe in recipes],
    )

    # 家族の誰かが「1 (苦手)」を付けた料理は出さない
    candidates = [
        recipe for recipe in recipes
        if 1 not in ratings.get(recipe.pk, [])
    ]

    recipe = None

    if candidates:
        recipe = random.choices(
            candidates,
            weights=[random_weight(ratings.get(item.pk)) for item in candidates],
            k=1,
        )[0]

    return render(
        request,
        "washoku/random_recipe.html",
        {
            "recipe": recipe,
            "mood": mood,
            "shop": shop,
            "moods": MoodTag.objects.all(),
            "shops": shop_choices(),
        },
    )


# =========================================================
# レシピ詳細・評価
# =========================================================

def recipe_detail(request, pk):

    recipes = visible_recipes(request.user)

    # 投稿した本人は、確認待ちの自分のレシピも見られる
    if request.user.is_authenticated:
        recipes = recipes | Recipe.objects.filter(submitted_by=request.user)

    recipe = get_object_or_404(
        recipes.distinct().prefetch_related(
            "mood_tags",
            Prefetch(
                "recipe_ingredients",
                queryset=RecipeIngredient.objects.select_related(
                    "ingredient"
                ).prefetch_related("ingredient__shops"),
            ),
        ),
        pk=pk,
    )

    my_rating = None
    member_ratings = []
    is_favorite = False
    note = None

    if request.user.is_authenticated:

        is_favorite = RecipeFavorite.objects.filter(user=request.user, recipe=recipe).exists()
        note = RecipeNote.objects.filter(user=request.user, recipe=recipe).first()

        members = family_members(request.user)

        by_user = dict(
            RecipeRating.objects.filter(
                recipe=recipe,
                user__in=members,
            ).values_list("user_id", "rating")
        )

        my_rating = by_user.get(request.user.pk)

        member_ratings = [
            {"user": member, "rating": by_user.get(member.pk)}
            for member in members
            if member.pk != request.user.pk
        ]

    shop = None

    if recipe.shop_rank is not None:
        shop = ShopType.objects.filter(rank=recipe.shop_rank).first()

    return render(
        request,
        "washoku/recipe_detail.html",
        {
            "recipe": recipe,
            "shop": shop,
            "main_items": [
                item for item in recipe.recipe_ingredients.all()
                if not item.is_seasoning
            ],
            "seasoning_items": [
                item for item in recipe.recipe_ingredients.all()
                if item.is_seasoning
            ],
            "related_posts": related_posts(
                [item.ingredient for item in recipe.recipe_ingredients.all()]
            ),
            **photo_context(request, recipe=recipe),
            "includes_rice": any(
                item.ingredient.name == "米" and "膳" in item.amount
                for item in recipe.recipe_ingredients.all()
            ),
            "my_rating": my_rating,
            "member_ratings": member_ratings,
            "is_favorite": is_favorite,
            "note": note,
            "rating_choices": RATING_CHOICES,
            **comment_context(request, recipe=recipe),
        },
    )


RATING_CHOICES = [
    (5, "大好き"),
    (4, "好き"),
    (3, "ふつう"),
    (2, "いまいち"),
    (1, "苦手"),
]


@login_required
@require_POST
def rate_recipe(request, pk):

    recipe = get_object_or_404(visible_recipes(request.user), pk=pk)

    value = request.POST.get("rating", "")

    if value == "clear":
        RecipeRating.objects.filter(user=request.user, recipe=recipe).delete()

    elif value.isdigit() and 1 <= int(value) <= 5:
        RecipeRating.objects.update_or_create(
            user=request.user,
            recipe=recipe,
            defaults={"rating": int(value)},
        )

    return redirect(reverse("washoku:recipe_detail", args=[recipe.pk]) + "#rating")


@login_required
@require_POST
def favorite_toggle(request, pk):

    recipe = get_object_or_404(visible_recipes(request.user), pk=pk)

    favorite, created = RecipeFavorite.objects.get_or_create(user=request.user, recipe=recipe)

    if not created:
        favorite.delete()

    return redirect(reverse("washoku:recipe_detail", args=[recipe.pk]))


@login_required
@require_POST
def note_save(request, pk):

    recipe = get_object_or_404(visible_recipes(request.user), pk=pk)

    body = request.POST.get("body", "").strip()[:2000]

    if body:
        RecipeNote.objects.update_or_create(user=request.user, recipe=recipe, defaults={"body": body})
        messages.success(request, "メモを保存しました。")
    else:
        RecipeNote.objects.filter(user=request.user, recipe=recipe).delete()
        messages.success(request, "メモを消しました。")

    return redirect(reverse("washoku:recipe_detail", args=[recipe.pk]) + "#note")


# =========================================================
# 食材
# =========================================================

def ingredient_list(request):

    query = request.GET.get("q", "").strip()

    ingredients = Ingredient.objects.prefetch_related(
        "shops",
        Prefetch("substitutes_for", queryset=published_substitutes()),
    )

    if query:
        ingredients = ingredients.filter(
            Q(name__icontains=query)
            | Q(name_de__icontains=query)
            | Q(name_fr__icontains=query)
            | Q(search_group__icontains=query)
            | Q(
                substitutes_for__original_name__icontains=query,
                substitutes_for__status="published",
            )
        ).distinct()

    by_category = defaultdict(list)

    for ingredient in ingredients.order_by("name"):
        by_category[ingredient.get_category_display()].append(ingredient)

    # 肉・魚・野菜… の順 (Ingredient.CATEGORY_CHOICES の順)
    order = [label for _value, label in Ingredient.CATEGORY_CHOICES]
    by_category = dict(sorted(by_category.items(), key=lambda item: order.index(item[0])))

    return render(
        request,
        "washoku/ingredient_list.html",
        {
            "by_category": dict(by_category),
            "query": query,
        },
    )


def ingredient_detail(request, pk):

    ingredient = get_object_or_404(
        Ingredient.objects.prefetch_related(
            "shops",
            Prefetch("substitutes_for", queryset=published_substitutes()),
        ),
        pk=pk,
    )

    recipes = (
        visible_recipes(request.user)
        .filter(ingredients=ingredient)
        .order_by("name")
    )

    return render(
        request,
        "washoku/ingredient_detail.html",
        {
            "ingredient": ingredient,
            "recipes": recipes,
            "related_posts": related_posts([ingredient]),
            **photo_context(request, ingredient=ingredient),
            **comment_context(request, ingredient=ingredient),
        },
    )


# =========================================================
# コメント・Q&A
# =========================================================

def comment_threads(comments, user):
    """
    先頭コメントとその返信をまとめる。
    非表示・削除済みは、返信が付いていれば「削除されました」として残す。
    """

    by_parent = defaultdict(list)
    roots = []

    for comment in comments:
        if comment.parent_id:
            by_parent[comment.parent_id].append(comment)
        else:
            roots.append(comment)

    def is_visible(comment):
        return not (comment.is_hidden or comment.is_deleted) or user.is_staff

    threads = []

    for root in roots:

        replies = [reply for reply in by_parent[root.pk] if is_visible(reply)]

        if not is_visible(root) and not replies:
            continue

        threads.append(
            {
                "comment": root,
                "replies": replies,
            }
        )

    return threads


def comment_context(request, recipe=None, ingredient=None, store=None, post=None):

    comments = (
        Comment.objects
        .filter(recipe=recipe, ingredient=ingredient, store=store, post=post)
        .select_related("author")
        .order_by("created_at", "pk")
    )

    reported_ids = set()

    if request.user.is_authenticated:
        reported_ids = set(
            CommentReport.objects.filter(
                reporter=request.user,
                comment__in=comments,
            ).values_list("comment_id", flat=True)
        )

    comments = list(comments)

    attach_reactions(comments, request.user)

    return {
        "threads": comment_threads(comments, request.user),
        "comment_form": CommentForm(),
        "reported_ids": reported_ids,
    }


def reaction_stamps(rows, user):
    """
    (対象の id, user_id, kind) の並びから、対象ごとのスタンプ一覧を作る。
    各スタンプは kind・label・emoji・count・mine を持つ。
    """

    counts = defaultdict(int)
    mine = set()

    for target_id, user_id, kind in rows:
        counts[target_id, kind] += 1
        if user.is_authenticated and user_id == user.pk:
            mine.add((target_id, kind))

    def stamps_for(target_id):
        return [
            {
                "kind": kind,
                "label": label,
                "emoji": REACTION_EMOJI[kind],
                "count": counts[target_id, kind],
                "mine": (target_id, kind) in mine,
            }
            for kind, label in REACTION_CHOICES
        ]

    return stamps_for


def attach_reactions(comments, user):
    """
    各コメントに stamps (スタンプの種類ごとの数と、自分が押したか) を付ける。
    """

    stamps_for = reaction_stamps(
        CommentReaction.objects.filter(
            comment__in=[comment.pk for comment in comments]
        ).values_list("comment_id", "user_id", "kind"),
        user,
    )

    for comment in comments:
        comment.stamps = stamps_for(comment.pk)


def toggle_reaction(model, user, kind, **target):
    """
    スタンプを押す / もう一度押すと取り消す。押したときだけ True を返す。
    """

    reaction, created = model.objects.get_or_create(user=user, kind=kind, **target)

    if not created:
        reaction.delete()

    return created


@login_required
@require_POST
def comment_react(request, pk):

    comment = get_object_or_404(
        Comment.objects.filter(is_hidden=False, is_deleted=False),
        pk=pk,
    )

    kind = request.POST.get("kind", "")

    # 自分のコメントには押せない
    if kind not in dict(REACTION_CHOICES) or comment.author_id == request.user.pk:
        return redirect(comment_target_url(comment))

    created = toggle_reaction(CommentReaction, request.user, kind, comment=comment)

    notify_stamp(
        created,
        request.user,
        kind,
        recipient_id=comment.author_id,
        target_text=f"あなたのコメント: {comment.body}",
        url=comment_target_url(comment),
        comment=comment,
    )

    return redirect(comment_target_url(comment))


@login_required
@require_POST
def post_react(request, pk):

    post = get_object_or_404(
        Post.objects.filter(status="published", kind="column"),
        pk=pk,
    )

    kind = request.POST.get("kind", "")

    # 自分のコラムには押せない
    url = reverse("washoku:post_detail", args=[post.pk]) + "#stamps"

    if kind in dict(REACTION_CHOICES) and post.author_id and post.author_id != request.user.pk:

        created = toggle_reaction(PostReaction, request.user, kind, post=post)

        notify_stamp(
            created,
            request.user,
            kind,
            recipient_id=post.author_id,
            target_text=f"あなたのコラム「{post.title}」",
            url=url,
            post=post,
        )

    return redirect(url)


def notify_stamp(created, actor, kind, recipient_id, target_text, url, **target):
    """
    スタンプが押されたら、どの種類でも書いた人に知らせる。
    取り消されたら、その通知も消す。
    """

    if not created:
        Notification.objects.filter(
            recipient_id=recipient_id,
            actor=actor,
            kind="stamp",
            stamp=kind,
            **target,
        ).delete()
        return

    Notification.objects.create(
        recipient_id=recipient_id,
        actor=actor,
        kind="stamp",
        stamp=kind,
        **target,
    )

    target_id = next(iter(target.values())).pk

    send_stamp_push(
        recipient_id,
        actor,
        dict(REACTION_CHOICES)[kind],
        target_text,
        url,
        f"washoku-stamp-{next(iter(target))}-{target_id}",
    )


def comment_target_url(comment):
    return comment.get_absolute_url()


def posted_too_recently(user):
    return Comment.objects.filter(
        author=user,
        created_at__gte=timezone.now() - COMMENT_INTERVAL,
    ).exists()


@login_required
@require_POST
def comment_create(request, target, pk):

    recipe = ingredient = store = post = None

    if target == "recipe":
        recipe = get_object_or_404(visible_recipes(request.user), pk=pk)
        back = reverse("washoku:recipe_detail", args=[pk])
    elif target == "ingredient":
        ingredient = get_object_or_404(Ingredient, pk=pk)
        back = reverse("washoku:ingredient_detail", args=[pk])
    elif target == "store":
        store = get_object_or_404(Store, pk=pk, is_active=True)
        back = reverse("washoku:store_detail", args=[pk])
    elif target == "post":
        post = get_object_or_404(Post, pk=pk, status="published")
        back = reverse("washoku:post_detail", args=[pk])
    else:
        raise Http404

    form = CommentForm(request.POST, request.FILES)

    if not form.is_valid():
        messages.error(request, "コメントを入力してください（500文字まで）。")
        return redirect(back + "#comments")

    if posted_too_recently(request.user):
        messages.error(request, "続けて投稿するときは1分ほど空けてください。")
        return redirect(back + "#comments")

    photo_url = ""

    if form.cleaned_data.get("photo"):
        try:
            photo_url = upload_photo(form.cleaned_data["photo"], "comments")
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect(back + "#comments")

    parent = None
    parent_id = request.POST.get("parent", "")

    if parent_id.isdigit():

        parent = get_object_or_404(
            Comment,
            pk=parent_id,
            recipe=recipe,
            ingredient=ingredient,
            store=store,
            post=post,
        )

        # 返信は1段だけ: 返信への返信は同じスレッドの末尾に付ける
        if parent.parent_id:
            parent = parent.parent

    comment = form.save(commit=False)
    comment.author = request.user
    # 管理者自身のコメントは「対応待ち」に出さない
    comment.admin_checked = request.user.is_staff
    comment.recipe = recipe
    comment.ingredient = ingredient
    comment.store = store
    comment.post = post
    comment.parent = parent
    comment.photo_url = photo_url

    if parent:
        comment.kind = "tip"

    comment.save()

    if parent:
        notify_reply(comment)

    return redirect(comment_target_url(comment))


# 管理者がページから写真を足せるもの: (モデル, 写真の項目, 保存先, ページの URL 名)
STAFF_PHOTO_TARGETS = {
    "store": (Store, ("photo_url",), "stores", "washoku:store_detail"),
}


# 会員が料理・食材の写真を投稿できる先: (モデル, 保存先のフォルダー, ページ)
MEMBER_PHOTO_TARGETS = {
    "recipe": (Recipe, "recipes", "washoku:recipe_detail"),
    "ingredient": (Ingredient, "ingredients", "washoku:ingredient_detail"),
}

# 1人が1日に投稿できる写真の数 (保存先の容量を守るため)
MEMBER_PHOTOS_PER_DAY = 10


def photo_context(request, recipe=None, ingredient=None):
    """
    ページに載っている写真を投稿した人と、写真の一覧 (管理者はすべて、会員は自分の分)。
    """

    item = recipe or ingredient
    shown = item.photo_1 if recipe else item.photo_url
    photos = list(item.member_photos.select_related("user"))
    shown_photo = next((photo for photo in photos if shown and photo.url == shown), None)

    if not request.user.is_staff:
        photos = [photo for photo in photos if request.user.is_authenticated and photo.user_id == request.user.pk]

    return {
        "photo_target": "recipe" if recipe else "ingredient",
        "shown_photo": shown_photo,
        "photo_list": photos,
    }


def show_photo(item, url):
    """
    料理・食材に載せる写真を url にする (空なら外す)。食材の Wikimedia の出典は消す。
    """

    if isinstance(item, Recipe):
        item.photo_1 = url
        item.save(update_fields=["photo_1"])
        return

    item.photo_url = url
    item.photo_credit = ""
    item.photo_source = ""
    item.save(update_fields=["photo_url", "photo_credit", "photo_source"])


@login_required
@require_POST
def photo_add(request, target, pk):
    """
    会員が料理・食材の写真を投稿する。まだ写真がなければそのまま載り、
    あれば候補として残して、管理者が選ぶ。
    """

    if target not in MEMBER_PHOTO_TARGETS:
        raise Http404

    model, folder, url_name = MEMBER_PHOTO_TARGETS[target]
    item = get_object_or_404(model, pk=pk)
    back = reverse(url_name, args=[pk])

    photo = request.FILES.get("photo")

    if not photo:
        return redirect(back)

    today = MemberPhoto.objects.filter(
        user=request.user,
        created_at__gte=timezone.now() - timedelta(days=1),
    ).count()

    if today >= MEMBER_PHOTOS_PER_DAY and not request.user.is_staff:
        messages.info(request, "今日はもう写真を投稿できません。また明日お願いします。")
        return redirect(back)

    try:
        url = upload_photo(photo, folder)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect(back)

    MemberPhoto.objects.create(user=request.user, url=url, **{target: item})

    current = item.photo_1 if target == "recipe" else item.photo_url

    if not current:
        show_photo(item, url)
        messages.success(request, "写真を載せました。ありがとうございます！")
        return redirect(back)

    messages.success(request, "写真を受け付けました。ありがとうございます！載せる写真は管理者が選びます。")

    if not request.user.is_staff:
        send_admin_alert(
            f"[スイスで和食] {item} に写真の候補が届きました",
            f"{request.build_absolute_uri(back)}\nページの「写真」から、載せる写真を選べます。",
        )

    return redirect(back)


@login_required
@require_POST
def photo_manage(request, pk):
    """
    show: 管理者がこの写真を載せる。delete: 管理者か投稿した本人が消す。
    載っている写真を消したら、残っている候補のうち一番古いものを載せる。
    """

    photo = get_object_or_404(MemberPhoto.objects.select_related("recipe", "ingredient"), pk=pk)
    item = photo.target
    action = request.POST.get("action")
    target = "recipe" if photo.recipe_id else "ingredient"
    back = reverse(MEMBER_PHOTO_TARGETS[target][2], args=[item.pk])

    if action == "show" and request.user.is_staff:
        show_photo(item, photo.url)
        messages.success(request, "この写真を載せました。")

    elif action == "delete" and (request.user.is_staff or photo.user_id == request.user.pk):

        was_shown = photo.is_shown
        photo.delete()
        delete_uploaded_photos(photo.url)

        if was_shown:
            oldest = item.member_photos.first()
            show_photo(item, oldest.url if oldest else "")

        messages.success(request, "写真を消しました。")

    else:
        raise Http404

    return redirect(back)


@login_required
@require_POST
def staff_photo(request, target, pk):
    """
    管理者だけ: レシピ・食材・お店のページで写真を追加・変更・削除する。
    """

    if not request.user.is_staff or target not in STAFF_PHOTO_TARGETS:
        raise Http404

    model, fields, folder, url_name = STAFF_PHOTO_TARGETS[target]
    item = get_object_or_404(model, pk=pk)
    back = reverse(url_name, args=[pk])

    field = request.POST.get("field", fields[0])

    if field not in fields:
        raise Http404

    old = getattr(item, field)
    photo = request.FILES.get("photo")

    if photo:
        try:
            setattr(item, field, upload_photo(photo, folder))
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect(back)
    elif request.POST.get("remove"):
        setattr(item, field, "")
    else:
        return redirect(back)

    update_fields = [field]

    # 食材の写真を自分の写真に変えたら、Wikimedia の出典は消す
    if target == "ingredient":
        item.photo_credit = ""
        item.photo_source = ""
        update_fields += ["photo_credit", "photo_source"]

    item.save(update_fields=update_fields)
    delete_uploaded_photos(old)

    messages.success(request, "写真を保存しました。" if photo else "写真を外しました。")

    return redirect(back)


def upload_form_photos(form, folder, names=("photo_1", "photo_2")):
    """
    フォームで選ばれた写真を順に保存して URL の一覧を返す。
    どれかが失敗したら、その項目にエラーを付け、保存済みの写真は消す。
    """

    urls = []

    for name in names:
        if form.cleaned_data.get(name):
            try:
                urls.append(upload_photo(form.cleaned_data[name], folder))
            except ValidationError as error:
                form.add_error(name, error)

    if form.errors:
        delete_uploaded_photos(*urls)
        return []

    return urls


def notify_reply(comment):
    """
    スレッドの先頭コメントの投稿者と、そのスレッドで返信した人に知らせる。
    """

    root = comment.parent

    recipients = {root.author_id}

    recipients.update(
        root.replies.exclude(pk=comment.pk).values_list("author_id", flat=True)
    )

    recipients.discard(comment.author_id)

    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=user_id,
                actor=comment.author,
                comment=comment,
            )
            for user_id in recipients
        ]
    )

    send_reply_push(comment, recipients)


def own_comment(request, pk):
    return get_object_or_404(
        Comment,
        pk=pk,
        author=request.user,
        is_deleted=False,
    )


@login_required
def comment_edit(request, pk):

    comment = own_comment(request, pk)

    if request.method == "POST":

        old_photo = comment.photo_url
        form = CommentEditForm(request.POST, request.FILES, instance=comment)

        if form.is_valid():

            comment = form.save(commit=False)

            try:
                if form.cleaned_data.get("photo"):
                    comment.photo_url = upload_photo(form.cleaned_data["photo"], "comments")
                elif form.cleaned_data.get("remove_photo"):
                    comment.photo_url = ""
            except ValidationError as error:
                form.add_error("photo", error)

        if form.is_valid():

            comment.edited_at = timezone.now()
            comment.save()

            if old_photo != comment.photo_url:
                delete_uploaded_photos(old_photo)

            return redirect(comment_target_url(comment))

    else:
        form = CommentEditForm(instance=comment)

    return render(
        request,
        "washoku/comment_edit.html",
        {
            "comment": comment,
            "form": form,
            "back_url": comment_target_url(comment),
        },
    )


@login_required
@require_POST
def comment_delete(request, pk):

    comment = own_comment(request, pk)

    back = comment_target_url(comment).split("#")[0] + "#comments"

    photo_url = comment.photo_url

    if comment.replies.exists():
        # 返信が付いていれば消さずに「削除されました」と表示する
        comment.is_deleted = True
        comment.photo_url = ""
        comment.save(update_fields=["is_deleted", "photo_url"])
    else:
        comment.delete()

    delete_uploaded_photos(photo_url)

    messages.success(request, "コメントを削除しました。")

    return redirect(back)


@login_required
@require_POST
def comment_report(request, pk):

    comment = get_object_or_404(Comment, pk=pk, is_deleted=False)

    if comment.author_id == request.user.pk:
        raise Http404

    with transaction.atomic():

        _, created = CommentReport.objects.get_or_create(
            comment=comment,
            reporter=request.user,
            defaults={"reason": request.POST.get("reason", "")[:200]},
        )

        if comment.reports.count() >= CommentReport.AUTO_HIDE_THRESHOLD:
            comment.is_hidden = True
            comment.save(update_fields=["is_hidden"])

    if created:
        messages.success(request, "通報しました。管理者が確認します。")

    return redirect(comment_target_url(comment))


def question_list(request):

    return render(
        request,
        "washoku/question_list.html",
        {
            "questions": open_questions()[:50],
            "answered": questions_with_answer_state().filter(has_answer=True)[:50],
        },
    )


@login_required
def notification_list(request):

    notifications = list(
        Notification.objects
        .filter(recipient=request.user)
        .select_related("actor", "post", "comment", "comment__recipe", "comment__ingredient", "comment__store", "comment__post")[:50]
    )

    for notification in notifications:
        if notification.comment:
            notification.url = comment_target_url(notification.comment)
        else:
            notification.url = reverse("washoku:post_detail", args=[notification.post_id])

    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)

    return render(
        request,
        "washoku/notification_list.html",
        {
            "notifications": notifications,
        },
    )


# =========================================================
# 家族
# =========================================================

@login_required
def family(request):

    membership = (
        HouseholdMember.objects
        .filter(user=request.user)
        .select_related("household")
        .first()
    )

    return render(
        request,
        "washoku/family.html",
        {
            "membership": membership,
            "members": family_members(request.user),
            "received_invites": HouseholdInvite.objects.filter(
                invited_user=request.user,
                status="pending",
            ).select_related("invited_by"),
            "sent_invites": HouseholdInvite.objects.filter(
                household=membership.household if membership else None,
                status="pending",
            ).select_related("invited_user") if membership else [],
        },
    )


@login_required
@require_POST
def family_invite(request):

    username = request.POST.get("username", "").strip()

    invited_user = get_user_model().objects.filter(
        username__iexact=username,
    ).first()

    if invited_user is None:
        messages.error(request, "そのユーザー名は見つかりませんでした。")
        return redirect("washoku:family")

    if invited_user == request.user:
        messages.error(request, "自分自身は招待できません。")
        return redirect("washoku:family")

    if HouseholdMember.objects.filter(user=invited_user).exists():
        messages.error(request, "そのユーザーはすでに家族に参加しています。")
        return redirect("washoku:family")

    with transaction.atomic():

        membership = HouseholdMember.objects.filter(
            user=request.user,
        ).select_related("household").first()

        # 初めて招待するときに家族を作る
        if membership is None:
            household = Household.objects.create(created_by=request.user)
            HouseholdMember.objects.create(household=household, user=request.user)
        else:
            household = membership.household

        _, created = HouseholdInvite.objects.get_or_create(
            household=household,
            invited_user=invited_user,
            status="pending",
            defaults={"invited_by": request.user},
        )

    if created:
        messages.success(request, f"{invited_user.username} さんを招待しました。")
    else:
        messages.error(request, "そのユーザーはすでに招待中です。")

    return redirect("washoku:family")


@login_required
@require_POST
@transaction.atomic
def family_respond(request, invite_id):

    invite = get_object_or_404(
        HouseholdInvite,
        pk=invite_id,
        invited_user=request.user,
        status="pending",
    )

    if request.POST.get("action") == "accept":

        if HouseholdMember.objects.filter(user=request.user).exists():
            messages.error(request, "すでに別の家族に参加しています。先に抜けてください。")
            return redirect("washoku:family")

        HouseholdMember.objects.create(
            household=invite.household,
            user=request.user,
        )

        invite.status = "accepted"
        invite.save(update_fields=["status", "updated_at"])

        HouseholdInvite.objects.filter(
            invited_user=request.user,
            status="pending",
        ).update(status="declined")

        messages.success(request, "家族に参加しました。")

    else:
        invite.status = "declined"
        invite.save(update_fields=["status", "updated_at"])

    return redirect("washoku:family")


@login_required
@require_POST
def family_leave(request):

    membership = HouseholdMember.objects.filter(
        user=request.user,
    ).select_related("household").first()

    if membership:

        household = membership.household
        membership.delete()

        if not household.members.exists():
            household.delete()

        messages.success(request, "家族から抜けました。")

    return redirect("washoku:family")


# =========================================================
# お店
# =========================================================

def store_list(request):

    kind = request.GET.get("kind", "")

    stores = Store.objects.filter(is_active=True).annotate(
        review_count=Count(
            "comments",
            filter=Q(comments__is_hidden=False, comments__is_deleted=False),
        )
    )

    if kind in dict(Store.KIND_CHOICES):
        stores = stores.filter(kind=kind)

    by_city = defaultdict(list)

    for store in stores.order_by("city", "area", "name"):
        by_city[store.city].append(store)

    # チューリッヒ市を先に、ほかの町はその後に
    by_city = dict(sorted(by_city.items(), key=lambda item: (item[0] != "Zürich", item[0])))

    return render(
        request,
        "washoku/store_list.html",
        {
            "by_city": by_city,
            "kind": kind,
            "kinds": Store.KIND_CHOICES,
        },
    )


def store_detail(request, pk):

    store = get_object_or_404(Store, pk=pk, is_active=True)

    return render(
        request,
        "washoku/store_detail.html",
        {
            "store": store,
            "photo_slots": [("photo_url", store.photo_url)],
            **comment_context(request, store=store),
        },
    )


# =========================================================
# 会員のレシピ投稿
# =========================================================

@login_required
def recipe_submit(request):

    pending = Recipe.objects.filter(submitted_by=request.user, status="draft").count()

    if pending >= MAX_PENDING_SUBMISSIONS:
        messages.info(
            request,
            f"確認待ちのレシピが{pending}品あります。掲載されてから、また投稿してください。",
        )
        return redirect("washoku:my_recipes")

    form = RecipeSubmissionForm(request.POST or None, request.FILES or None)

    photos = []

    if request.method == "POST" and form.is_valid():
        photos = upload_form_photos(form, "recipes")

    if request.method == "POST" and form.is_valid():

        with transaction.atomic():

            recipe = form.save(commit=False)
            recipe.photo_1 = photos[0] if photos else ""
            recipe.status = "draft"
            recipe.origin = "member"
            recipe.submitted_by = request.user
            recipe.submitted_ingredients = form.cleaned_data["ingredients_text"]
            recipe.save()
            form.save_m2m()

            for url in photos:
                MemberPhoto.objects.create(recipe=recipe, url=url, user=request.user)

            linked = set()

            for order, (ingredient, _name, amount) in enumerate(form.parsed_ingredients(), start=1):

                if ingredient is None or ingredient.pk in linked:
                    continue

                linked.add(ingredient.pk)

                RecipeIngredient.objects.create(
                    recipe=recipe,
                    ingredient=ingredient,
                    amount=amount[:100],
                    is_seasoning=ingredient.category == "seasoning",
                    display_order=order,
                )

            recipe.update_shop_rank()

        send_admin_alert(
            "新しいレシピの投稿",
            f"{recipe.name}（{request.user.username} さん）\n\n"
            + request.build_absolute_uri(
                reverse("admin:washoku_recipe_change", args=[recipe.pk])
            ),
        )

        messages.success(
            request,
            "投稿ありがとうございます！管理者が確認してから掲載します。",
        )

        return redirect("washoku:recipe_detail", pk=recipe.pk)

    return render(
        request,
        "washoku/recipe_submit.html",
        {
            "form": form,
        },
    )


@login_required
def my_recipes(request):

    recipes = (
        Recipe.objects
        .filter(submitted_by=request.user)
        .order_by("-created_at")
    )

    return render(
        request,
        "washoku/my_recipes.html",
        {
            "recipes": recipes,
        },
    )


# =========================================================
# このアプリについて・マイページ
# =========================================================

def about(request):

    form = FeedbackForm()

    url = reverse("washoku:about")

    if request.method == "POST":

        form = FeedbackForm(request.POST)

        last_sent = request.session.get("washoku_feedback_sent_at", 0)

        if timezone.now().timestamp() - last_sent < FEEDBACK_INTERVAL_SECONDS:
            return redirect(f"{url}?sent=wait#feedback")

        if form.is_valid():

            # 隠し項目 (website) が埋まっているのはボットなので保存しない
            if not form.cleaned_data.get("website"):

                feedback = form.save()

                send_admin_alert(
                    "新しいご意見・ご要望",
                    f"{feedback.message}\n\n"
                    + request.build_absolute_uri(
                        reverse("admin:washoku_feedback_changelist")
                    ),
                )

            request.session["washoku_feedback_sent_at"] = timezone.now().timestamp()

            return redirect(f"{url}?sent=1#feedback")

    return render(
        request,
        "washoku/about.html",
        {
            "feedback_form": form,
            "feedback_sent": request.GET.get("sent", ""),
        },
    )


def my_page(request):

    from django.conf import settings

    context = {
        "vapid_public_key": settings.VAPID_PUBLIC_KEY or "",
    }

    if request.user.is_authenticated:
        context.update(
            {
                "favorite_count": RecipeFavorite.objects.filter(
                    user=request.user,
                    recipe__in=visible_recipes(request.user),
                ).count(),
                "rated_count": RecipeRating.objects.filter(
                    user__in=family_members(request.user),
                    recipe__in=visible_recipes(request.user),
                ).values("recipe").distinct().count(),
                "note_count": RecipeNote.objects.filter(user=request.user).count(),
                "comment_count": Comment.objects.filter(
                    author=request.user,
                    is_deleted=False,
                ).count(),
                "submitted_count": Recipe.objects.filter(
                    submitted_by=request.user,
                ).count(),
                "post_count": Post.objects.filter(
                    author=request.user,
                ).count(),
                "family_count": len(family_members(request.user)),
                "invite_count": HouseholdInvite.objects.filter(
                    invited_user=request.user,
                    status="pending",
                ).count(),
            }
        )

    return render(
        request,
        "washoku/my_page.html",
        context,
    )


FAVORITE_SORTS = [
    ("new", "保存した順"),
    ("family", "家族の評価順"),
]


@login_required
def my_favorites(request):
    """
    お気に入りに保存したレシピ。家族の評価順にも並べられる。
    """

    sort = request.GET.get("sort", "new")

    favorites = list(
        RecipeFavorite.objects
        .filter(user=request.user, recipe__in=visible_recipes(request.user))
        .select_related("recipe")
    )

    recipes = attach_family_rating([favorite.recipe for favorite in favorites], request.user)

    if sort == "family":
        recipes.sort(
            key=lambda recipe: (recipe.family_average is None, -(recipe.family_average or 0), recipe.name)
        )

    return render(
        request,
        "washoku/my_favorites.html",
        {
            "recipes": recipes,
            "sort": sort,
            "sorts": FAVORITE_SORTS,
        },
    )


@login_required
def family_favorites(request):
    """
    家族の好きな料理を、家族の平均評価が高い順に。
    評価は自分と家族のメンバーにしか見えない。
    """

    members = family_members(request.user)

    ratings = (
        RecipeRating.objects
        .filter(user__in=members, recipe__in=visible_recipes(request.user))
        .select_related("recipe")
    )

    by_recipe = {}

    for rating in ratings:
        entry = by_recipe.setdefault(rating.recipe_id, {"recipe": rating.recipe, "ratings": {}})
        entry["ratings"][rating.user_id] = rating.rating

    favorite_ids = set(
        RecipeFavorite.objects.filter(user=request.user).values_list("recipe_id", flat=True)
    )

    rows = []

    for entry in by_recipe.values():

        values = list(entry["ratings"].values())

        rows.append(
            {
                "recipe": entry["recipe"],
                "average": sum(values) / len(values),
                "rated": len(values),
                "members": [
                    {"user": member, "rating": entry["ratings"].get(member.pk)}
                    for member in members
                ],
                "is_favorite": entry["recipe"].pk in favorite_ids,
            }
        )

    rows.sort(key=lambda row: (-row["average"], -row["rated"], row["recipe"].name))

    # お気に入りの一覧と同じカードで出す (カードの星は家族の平均)
    for row in rows:
        row["recipe"].family_average = row["average"]

    return render(
        request,
        "washoku/family_favorites.html",
        {
            "rows": rows,
            "has_family": len(members) > 1,
        },
    )


@login_required
def my_notes(request):

    notes = (
        RecipeNote.objects
        .filter(user=request.user)
        .select_related("recipe")
    )

    return render(
        request,
        "washoku/my_notes.html",
        {
            "notes": notes,
        },
    )


@login_required
def my_comments(request):

    comments = list(
        Comment.objects
        .filter(author=request.user, is_deleted=False)
        .select_related("recipe", "ingredient", "store", "post")
        .order_by("-created_at")[:100]
    )

    for comment in comments:
        comment.url = comment_target_url(comment)

    return render(
        request,
        "washoku/my_comments.html",
        {
            "comments": comments,
        },
    )


# =========================================================
# 日本の食材の代わり
# =========================================================

def published_substitutes():
    return Substitute.objects.filter(status="published")


def substitute_list(request):
    """
    日本の食材 → スイスで代わりに使えるもの、の一覧。会員も投稿できる。
    """

    query = request.GET.get("q", "").strip()

    substitutes = published_substitutes().select_related("substitute", "submitted_by")

    if query:
        substitutes = substitutes.filter(
            Q(original_name__icontains=query)
            | Q(substitute__name__icontains=query)
            | Q(substitute__name_de__icontains=query)
            | Q(substitute_name__icontains=query)
            | Q(tips__icontains=query)
        )

    by_category = defaultdict(list)

    for item in substitutes.order_by("original_name"):
        category = (
            item.substitute.get_category_display()
            if item.substitute_id
            else "みんなが見つけた代用品"
        )
        by_category[category].append(item)

    # 野菜・きのこを先に、みんなの投稿 (食材リストにないもの) は最後に
    order = ["野菜", "きのこ"] + [
        label for _value, label in Ingredient.CATEGORY_CHOICES
        if label not in ("野菜", "きのこ")
    ] + ["みんなが見つけた代用品"]
    by_category = dict(
        sorted(by_category.items(), key=lambda item: order.index(item[0]))
    )

    form = SubstituteForm()

    return render(
        request,
        "washoku/substitute_list.html",
        {
            "by_category": by_category,
            "query": query,
            "total": sum(len(items) for items in by_category.values()),
            "form": form,
        },
    )


@login_required
def substitute_submit(request):

    pending = Substitute.objects.filter(submitted_by=request.user, status="draft").count()

    if pending >= MAX_PENDING_SUBMISSIONS:
        messages.info(request, f"確認待ちの代用品が{pending}件あります。掲載されてから、また投稿してください。")
        return redirect(reverse("washoku:substitute_list") + "#suggest")

    form = SubstituteForm(request.POST or None)

    if request.method == "POST" and form.is_valid():

        substitute = form.save(commit=False)
        substitute.submitted_by = request.user
        substitute.status = "published" if request.user.is_staff else "draft"
        substitute.save()

        if substitute.status == "draft":

            send_admin_alert(
                "新しい代用品の投稿",
                f"{substitute}（{request.user.username} さん）\n\n"
                + request.build_absolute_uri(
                    reverse("admin:washoku_substitute_change", args=[substitute.pk])
                ),
            )

            messages.success(request, "教えてくれてありがとうございます！管理者が確認してから掲載します。")

        return redirect(reverse("washoku:substitute_list") + "#suggest")

    return render(
        request,
        "washoku/substitute_submit.html",
        {
            "form": form,
        },
    )


# =========================================================
# みんなの投稿 (コラム・おすすめ商品)
# =========================================================

POST_KIND_TEXT = {
    "column": {
        "url_name": "washoku:column_list",
        "heading": "みんなのコラム",
        "lead": "スイスでの買い物や料理の工夫、失敗談などです。",
        "new_label": "コラムを書く",
    },
    "product": {
        "url_name": "washoku:product_list",
        "heading": "スーパーのおすすめ商品",
        "lead": "スーパーやアジアの店で買える、日本の味に近い商品です。",
        "new_label": "商品を紹介する",
    },
    "link": {
        "url_name": "washoku:link_list",
        "heading": "参考リンク",
        "lead": "ほかのサイトの役に立つ記事です。要点と出典を載せています。",
        "new_label": "リンクを紹介する",
    },
}


def ingredient_group_filter(prefix, ingredients):
    """
    食材 (と同じ検索グループの食材) に当てはまる条件。prefix は関係名 (例: "ingredients__")。
    """

    groups = {ingredient.group_name for ingredient in ingredients}

    return (
        Q(**{f"{prefix}search_group__in": groups})
        | Q(**{f"{prefix}search_group": "", f"{prefix}name__in": groups})
    )


def related_posts(ingredients, limit=5):
    """
    これらの食材に関係するコラム・参考リンクなど (公開済み、新しい順)。
    """

    if not ingredients:
        return []

    return list(
        Post.objects
        .filter(status="published")
        .filter(ingredient_group_filter("ingredients__", ingredients))
        .distinct()
        .order_by("-created_at")[:limit]
    )


def related_recipes(user, post, limit=6):
    """
    投稿に選んだ食材を使うレシピ。
    """

    ingredients = list(post.ingredients.all())

    if not ingredients:
        return []

    return list(
        visible_recipes(user)
        .filter(ingredient_group_filter("ingredients__", ingredients))
        .distinct()
        .order_by("name")[:limit]
    )


def visible_posts(user):

    posts = Post.objects.all()

    if user.is_staff:
        return posts

    if user.is_authenticated:
        return posts.filter(Q(status="published") | Q(author=user))

    return posts.filter(status="published")


def post_list(request, kind):

    posts = (
        Post.objects
        .filter(kind=kind, status="published")
        .select_related("author")
        .annotate(
            comment_count=Count(
                "comments",
                filter=Q(comments__is_hidden=False, comments__is_deleted=False),
            )
        )
    )

    shop = request.GET.get("shop", "")
    section = request.GET.get("section", "")

    if kind == "product":

        # お店のコードはどれもほかのコードの一部ではないので、含むかどうかで絞れる
        if shop in dict(Post.SHOP_CHOICES):
            posts = posts.filter(shop__contains=shop)

        if section in dict(Post.SECTION_CHOICES):
            posts = posts.filter(section=section)

    return render(
        request,
        "washoku/post_list.html",
        {
            "kind": kind,
            "text": POST_KIND_TEXT[kind],
            "posts": posts,
            "shop": shop,
            "section": section,
            "shops": Post.SHOP_CHOICES,
            "sections": Post.SECTION_CHOICES,
        },
    )


def column_list(request):
    return post_list(request, "column")


def product_list(request):
    return post_list(request, "product")


def link_list(request):
    return post_list(request, "link")


def post_detail(request, pk):

    post = get_object_or_404(
        visible_posts(request.user).select_related("author"),
        pk=pk,
    )

    return render(
        request,
        "washoku/post_detail.html",
        {
            "post": post,
            "text": POST_KIND_TEXT[post.kind],
            "related_recipes": related_recipes(request.user, post),
            "other_columns": latest_columns(exclude=post) if post.kind == "column" else [],
            "stamps": reaction_stamps(
                post.reactions.values_list("post_id", "user_id", "kind"),
                request.user,
            )(post.pk),
            **comment_context(request, post=post),
        },
    )


@login_required
def post_submit(request, kind):

    if kind not in POST_KIND_TEXT:
        raise Http404

    pending = Post.objects.filter(author=request.user, kind=kind, status="draft").count()

    if pending >= MAX_PENDING_SUBMISSIONS:
        messages.info(
            request,
            f"確認待ちの投稿が{pending}件あります。掲載されてから、また投稿してください。",
        )
        return redirect("washoku:my_posts")

    form = PostForm(request.POST or None, request.FILES or None, kind=kind)

    photos = []

    if request.method == "POST" and form.is_valid():
        photos = upload_form_photos(form, "columns")

    if request.method == "POST" and form.is_valid():

        post = form.save(commit=False)
        post.kind = kind
        post.photo_1, post.photo_2 = (photos + ["", ""])[:2]
        post.author = request.user
        # 管理者の投稿はそのまま公開する
        post.status = "published" if request.user.is_staff else "draft"
        post.save()

        if post.status == "draft":

            send_admin_alert(
                f"新しい{post.get_kind_display()}の投稿",
                f"{post.title}（{request.user.username} さん）\n\n"
                + request.build_absolute_uri(
                    reverse("admin:washoku_post_change", args=[post.pk])
                ),
            )

            messages.success(
                request,
                "投稿ありがとうございます！管理者が確認してから掲載します。",
            )

        return redirect(post.get_absolute_url())

    return render(
        request,
        "washoku/post_submit.html",
        {
            "form": form,
            "kind": kind,
            "text": POST_KIND_TEXT[kind],
        },
    )


@login_required
def my_posts(request):

    posts = (
        Post.objects
        .filter(author=request.user)
        .order_by("-created_at")
    )

    return render(
        request,
        "washoku/my_posts.html",
        {
            "posts": posts,
        },
    )


# =========================================================
# みんなの投稿・コメント (時系列で)
# =========================================================

ACTIVITY_PER_PAGE = 30


def activity_entries(comment_limit=300, post_limit=100):
    """
    公開中のコメントとみんなの投稿を、新しい順に1つの列にする。
    """

    comments = (
        Comment.objects
        .filter(is_hidden=False, is_deleted=False)
        .filter(public_comment_targets())
        .select_related("recipe", "ingredient", "store", "post", "author", "parent")
        .order_by("-created_at")[:comment_limit]
    )

    posts = (
        Post.objects
        .filter(status="published")
        .select_related("author")
        .order_by("-created_at")[:post_limit]
    )

    items = [{"kind": "comment", "item": comment, "at": comment.created_at} for comment in comments]
    items += [{"kind": "post", "item": post, "at": post.created_at} for post in posts]
    items.sort(key=lambda entry: entry["at"], reverse=True)

    return items


def activity(request):

    items = activity_entries()

    from django.core.paginator import Paginator

    page = Paginator(items, ACTIVITY_PER_PAGE).get_page(request.GET.get("page"))

    return render(
        request,
        "washoku/activity.html",
        {
            "page": page,
        },
    )


# =========================================================
# 全体の検索
# =========================================================

SEARCH_LIMIT = 20


def search(request):

    query = request.GET.get("q", "").strip()[:100]

    results = []

    if query:

        recipes = (
            visible_recipes(request.user)
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(ingredients__name__icontains=query)
                | Q(ingredients__name_de__icontains=query)
                | Q(ingredients__search_group__icontains=query)
            )
            .distinct()
            .order_by("name")
        )

        ingredients = (
            Ingredient.objects
            .filter(
                Q(name__icontains=query)
                | Q(name_de__icontains=query)
                | Q(search_group__icontains=query)
            )
            .order_by("name")
        )

        substitutes = (
            published_substitutes()
            .filter(
                Q(original_name__icontains=query)
                | Q(substitute__name__icontains=query)
                | Q(substitute__name_de__icontains=query)
                | Q(substitute_name__icontains=query)
            )
            .select_related("substitute")
            .order_by("original_name")
        )

        stores = (
            Store.objects
            .filter(is_active=True)
            .filter(
                Q(name__icontains=query)
                | Q(city__icontains=query)
                | Q(area__icontains=query)
                | Q(description__icontains=query)
            )
            .order_by("name")
        )

        posts = (
            Post.objects
            .filter(status="published")
            .filter(Q(title__icontains=query) | Q(body__icontains=query) | Q(resembles__icontains=query))
        )

        comments = (
            Comment.objects
            .filter(is_hidden=False, is_deleted=False, body__icontains=query)
            .filter(public_comment_targets())
            .select_related("recipe", "ingredient", "store", "post", "author")
            .order_by("-created_at")
        )

        results = [
            ("レシピ", "recipe", list(recipes[:SEARCH_LIMIT])),
            ("食材", "ingredient", list(ingredients[:SEARCH_LIMIT])),
            ("日本の食材の代わり", "substitute", list(substitutes[:SEARCH_LIMIT])),
            ("お店", "store", list(stores[:SEARCH_LIMIT])),
            ("コラム・おすすめ商品", "post", list(posts[:SEARCH_LIMIT])),
            ("コメント・質問", "comment", list(comments[:SEARCH_LIMIT])),
        ]

        results = [group for group in results if group[2]]

    return render(
        request,
        "washoku/search.html",
        {
            "query": query,
            "results": results,
            "result_count": sum(len(group[2]) for group in results),
        },
    )


# =========================================================
# プッシュ通知 (返信のお知らせ)
# =========================================================

@login_required
@require_POST
def push_subscribe(request):

    from news.push_views import parse_subscription

    data = parse_subscription(request)

    if data is None:
        return JsonResponse({"error": "Invalid subscription."}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=data["endpoint"],
        defaults={
            "user": request.user,
            "p256dh": data["p256dh"],
            "auth": data["auth"],
        },
    )

    return JsonResponse({"success": True})


@login_required
@require_POST
def push_unsubscribe(request):

    try:
        endpoint = json.loads(request.body).get("endpoint")
    except (ValueError, UnicodeDecodeError, AttributeError):
        endpoint = None

    if not isinstance(endpoint, str) or not endpoint:
        return JsonResponse({"error": "Invalid endpoint."}, status=400)

    PushSubscription.objects.filter(endpoint=endpoint, user=request.user).delete()

    return JsonResponse({"success": True})
