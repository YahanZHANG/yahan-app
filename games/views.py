import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import (
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import render
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from .models import GameScore


# =========================================================
# Constants
# =========================================================

PUBLIC_USER_GROUP = "public_users"


# =========================================================
# Helpers
# =========================================================

def get_display_name(user):

    try:
        profile = user.profile

    except ObjectDoesNotExist:
        return user.username

    return profile.display_name


def is_public_user(user):

    return (
        user.is_authenticated
        and not user.is_superuser
        and user.groups.filter(
            name=PUBLIC_USER_GROUP
        ).exists()
    )


def can_access_game(user, game):

    # -----------------------------------------------------
    # マアアアリオだけ一般公開しない
    # -----------------------------------------------------

    if (
        game == GameScore.Game.MAAARIO
        and is_public_user(user)
    ):
        return False

    return True


def normalise_level(
    game,
    raw_level,
):

    if game in (
        GameScore.Game.BLOCK_BREAKER,
        GameScore.Game.TAP_STAR,
        GameScore.Game.MAZE_CHASE,
        GameScore.Game.MAAARIO,
    ):

        try:
            level = int(
                raw_level
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

        if 1 <= level <= 5:
            return level

    return None


def get_ranking_data(
    user,
    game,
    level,
):

    base_queryset = (
        GameScore.objects
        .filter(
            game=game,
            level=level,
        )
        .select_related(
            "user",
            "user__profile",
        )
        .order_by(
            "-score",
            "updated_at",
            "id",
        )
    )


    top_scores = list(
        base_queryset[:5]
    )


    entries = []

    for index, item in enumerate(
        top_scores,
        start=1,
    ):

        entries.append(
            {
                "rank": index,
                "name": get_display_name(
                    item.user
                ),
                "score": item.score,
                "is_me": (
                    item.user_id
                    == user.id
                ),
            }
        )


    personal_score = (
        base_queryset
        .filter(
            user=user
        )
        .first()
    )


    if personal_score is None:

        personal_best = None
        personal_rank = None

    else:

        personal_best = (
            personal_score.score
        )

        better_score_count = (
            GameScore.objects
            .filter(
                game=game,
                level=level,
                score__gt=personal_best,
            )
            .count()
        )

        personal_rank = (
            better_score_count + 1
        )


    return {
        "entries": entries,
        "personal_best": personal_best,
        "personal_rank": personal_rank,
    }


# =========================================================
# Game list
# =========================================================

@login_required
def game_list(request):

    return render(
        request,
        "games/index.html",
        {
            "is_public_user": is_public_user(
                request.user
            ),
        },
    )

# =========================================================
# Block Breaker
# =========================================================

@login_required
def block_breaker(request):

    ranking = get_ranking_data(
        request.user,
        GameScore.Game.BLOCK_BREAKER,
        1,
    )

    context = {
        "ranking_entries": (
            ranking["entries"]
        ),
        "personal_best": (
            ranking["personal_best"]
        ),
        "personal_rank": (
            ranking["personal_rank"]
        ),
    }

    return render(
        request,
        "games/block_breaker/index.html",
        context,
    )


# =========================================================
# Tap Star
# =========================================================

@login_required
def tap_star(request):

    ranking = get_ranking_data(
        request.user,
        GameScore.Game.TAP_STAR,
        1,
    )

    context = {
        "ranking_entries": (
            ranking["entries"]
        ),
        "personal_best": (
            ranking["personal_best"]
        ),
        "personal_rank": (
            ranking["personal_rank"]
        ),
    }

    return render(
        request,
        "games/tap_star/index.html",
        context,
    )


# =========================================================
# Maze Chase
# =========================================================

@login_required
def maze_chase(request):

    ranking = get_ranking_data(
        request.user,
        GameScore.Game.MAZE_CHASE,
        1,
    )

    context = {
        "ranking_entries": (
            ranking["entries"]
        ),
        "personal_best": (
            ranking["personal_best"]
        ),
        "personal_rank": (
            ranking["personal_rank"]
        ),
    }

    return render(
        request,
        "games/maze_chase/index.html",
        context,
    )


# =========================================================
# Maaario
# =========================================================

@login_required
def maaario(request):

    # -----------------------------------------------------
    # 一般登録ユーザーは利用不可
    # -----------------------------------------------------

    if not can_access_game(
        request.user,
        GameScore.Game.MAAARIO,
    ):

        return HttpResponseForbidden(
            "このゲームは現在、一般公開していません。"
        )


    ranking = get_ranking_data(
        request.user,
        GameScore.Game.MAAARIO,
        1,
    )

    context = {
        "ranking_entries": (
            ranking["entries"]
        ),
        "personal_best": (
            ranking["personal_best"]
        ),
        "personal_rank": (
            ranking["personal_rank"]
        ),
    }

    return render(
        request,
        "games/maaario/index.html",
        context,
    )


# =========================================================
# Save score API
# =========================================================

@login_required
@require_POST
def save_score(request):

    try:

        data = json.loads(
            request.body.decode(
                "utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid JSON.",
            },
            status=400,
        )


    game = data.get(
        "game"
    )


    if game not in GameScore.Game.values:

        return JsonResponse(
            {
                "ok": False,
                "error": "Unknown game.",
            },
            status=400,
        )


    # -----------------------------------------------------
    # Private game protection
    # -----------------------------------------------------

    if not can_access_game(
        request.user,
        game,
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": "This game is not available.",
            },
            status=403,
        )


    try:

        score = int(
            data.get(
                "score"
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid score.",
            },
            status=400,
        )


    if (
        score < 0
        or score > 1_000_000
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid score.",
            },
            status=400,
        )


    level = normalise_level(
        game,
        data.get(
            "level"
        ),
    )


    if level is None:

        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid level.",
            },
            status=400,
        )


    with transaction.atomic():

        game_score, created = (
            GameScore.objects
            .get_or_create(
                user=request.user,
                game=game,
                level=level,
                defaults={
                    "score": score,
                },
            )
        )


        is_new_best = created


        if (
            not created
            and score > game_score.score
        ):

            game_score.score = score

            game_score.save()

            is_new_best = True


    ranking_data = (
        get_ranking_data(
            request.user,
            game,
            level,
        )
    )


    return JsonResponse(
        {
            "ok": True,
            "is_new_best": is_new_best,
            "submitted_score": score,
            **ranking_data,
        }
    )


# =========================================================
# Ranking API
# =========================================================

@login_required
@require_GET
def ranking(
    request,
    game,
):

    if game not in GameScore.Game.values:

        return JsonResponse(
            {
                "ok": False,
                "error": "Unknown game.",
            },
            status=404,
        )


    # -----------------------------------------------------
    # Private game protection
    # -----------------------------------------------------

    if not can_access_game(
        request.user,
        game,
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": "This game is not available.",
            },
            status=403,
        )


    level = normalise_level(
        game,
        request.GET.get(
            "level"
        ),
    )


    if level is None:

        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid level.",
            },
            status=400,
        )


    ranking_data = (
        get_ranking_data(
            request.user,
            game,
            level,
        )
    )


    return JsonResponse(
        {
            "ok": True,
            **ranking_data,
        }
    )