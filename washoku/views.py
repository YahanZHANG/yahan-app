import random

from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CommentEditForm, CommentForm
from .models import (
    Comment,
    CommentReport,
    Household,
    HouseholdInvite,
    HouseholdMember,
    Ingredient,
    MoodTag,
    Notification,
    Recipe,
    RecipeIngredient,
    RecipeRating,
    ShopType,
)


# 同じ人が続けてコメントできるまでの間隔
COMMENT_INTERVAL = timedelta(seconds=60)


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


def open_questions():
    """
    返信がまだない質問 (新しい順)。
    """

    answered = Comment.objects.filter(
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
        .filter(
            Q(recipe__status="published") | Q(ingredient__isnull=False)
        )
        .annotate(has_answer=Exists(answered))
        .filter(has_answer=False)
        .select_related("recipe", "ingredient", "author")
        .order_by("-created_at")
    )


# =========================================================
# ホーム
# =========================================================

def home(request):

    recipes = visible_recipes(request.user)

    latest = recipe_card_queryset(
        recipes.order_by("-created_at")
    )[:6]

    latest_comments = (
        Comment.objects
        .filter(
            is_hidden=False,
            is_deleted=False,
        )
        .filter(
            Q(recipe__status="published") | Q(ingredient__isnull=False)
        )
        .select_related("recipe", "ingredient", "author")
        .order_by("-created_at")[:5]
    )

    return render(
        request,
        "washoku/home.html",
        {
            "latest_recipes": attach_family_rating(latest, request.user),
            "latest_comments": latest_comments,
            "questions": open_questions()[:5],
            "moods": MoodTag.objects.all(),
            "categories": Recipe.CATEGORY_CHOICES[:-1],
            "recipe_count": recipes.count(),
        },
    )


# =========================================================
# 一覧・検索
# =========================================================

SORT_CHOICES = [
    ("name", "名前順"),
    ("new", "新しい順"),
    ("time", "早くできる順"),
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

    if sort == "new":
        recipes = recipes.order_by("-created_at")
    elif sort == "time":
        recipes = recipes.order_by("cooking_time_minutes", "name")
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
            "time_choices": [(15, "15分以内"), (30, "30分以内"), (60, "1時間以内")],
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

    selected = request.GET.getlist("g")
    selected_set = set(selected)

    results = []

    if selected_set:

        main_items = RecipeIngredient.objects.filter(
            is_seasoning=False,
            is_optional=False,
        ).select_related("ingredient")

        recipes = visible_recipes(request.user).prefetch_related(
            Prefetch("recipe_ingredients", queryset=main_items, to_attr="main_items")
        )

        for recipe in recipes:

            names = [item.ingredient.group_name for item in recipe.main_items]

            have = [name for name in names if name in selected_set]

            if not have:
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

    recipe = get_object_or_404(
        visible_recipes(request.user).prefetch_related(
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

    if request.user.is_authenticated:

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
            "my_rating": my_rating,
            "member_ratings": member_ratings,
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


# =========================================================
# 食材
# =========================================================

def ingredient_list(request):

    query = request.GET.get("q", "").strip()

    ingredients = Ingredient.objects.prefetch_related(
        "shops",
        "substitutes_for",
    )

    if query:
        ingredients = ingredients.filter(
            Q(name__icontains=query)
            | Q(name_de__icontains=query)
            | Q(name_fr__icontains=query)
            | Q(search_group__icontains=query)
            | Q(substitutes_for__original_name__icontains=query)
        ).distinct()

    by_category = defaultdict(list)

    for ingredient in ingredients.order_by("category", "name"):
        by_category[ingredient.get_category_display()].append(ingredient)

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
        Ingredient.objects.prefetch_related("shops", "substitutes_for"),
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


def comment_context(request, recipe=None, ingredient=None):

    comments = (
        Comment.objects
        .filter(recipe=recipe, ingredient=ingredient)
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

    return {
        "threads": comment_threads(comments, request.user),
        "comment_form": CommentForm(),
        "reported_ids": reported_ids,
    }


def comment_target_url(comment):

    if comment.recipe_id:
        url = reverse("washoku:recipe_detail", args=[comment.recipe_id])
    else:
        url = reverse("washoku:ingredient_detail", args=[comment.ingredient_id])

    return f"{url}#comment-{comment.pk}"


def posted_too_recently(user):
    return Comment.objects.filter(
        author=user,
        created_at__gte=timezone.now() - COMMENT_INTERVAL,
    ).exists()


@login_required
@require_POST
def comment_create(request, target, pk):

    if target == "recipe":
        recipe = get_object_or_404(visible_recipes(request.user), pk=pk)
        ingredient = None
        back = reverse("washoku:recipe_detail", args=[pk])
    elif target == "ingredient":
        recipe = None
        ingredient = get_object_or_404(Ingredient, pk=pk)
        back = reverse("washoku:ingredient_detail", args=[pk])
    else:
        raise Http404

    form = CommentForm(request.POST)

    if not form.is_valid():
        messages.error(request, "コメントを入力してください（500文字まで）。")
        return redirect(back + "#comments")

    if posted_too_recently(request.user):
        messages.error(request, "続けて投稿するときは1分ほど空けてください。")
        return redirect(back + "#comments")

    parent = None
    parent_id = request.POST.get("parent", "")

    if parent_id.isdigit():

        parent = get_object_or_404(
            Comment,
            pk=parent_id,
            recipe=recipe,
            ingredient=ingredient,
        )

        # 返信は1段だけ: 返信への返信は同じスレッドの末尾に付ける
        if parent.parent_id:
            parent = parent.parent

    comment = form.save(commit=False)
    comment.author = request.user
    comment.recipe = recipe
    comment.ingredient = ingredient
    comment.parent = parent

    if parent:
        comment.kind = "tip"

    comment.save()

    if parent:
        notify_reply(comment)

    return redirect(comment_target_url(comment))


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

        form = CommentEditForm(request.POST, instance=comment)

        if form.is_valid():

            comment = form.save(commit=False)
            comment.edited_at = timezone.now()
            comment.save()

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

    if comment.replies.exists():
        # 返信が付いていれば消さずに「削除されました」と表示する
        comment.is_deleted = True
        comment.save(update_fields=["is_deleted"])
    else:
        comment.delete()

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
        },
    )


@login_required
def notification_list(request):

    notifications = list(
        Notification.objects
        .filter(recipient=request.user)
        .select_related("actor", "comment", "comment__recipe", "comment__ingredient")[:50]
    )

    for notification in notifications:
        notification.url = comment_target_url(notification.comment)

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
