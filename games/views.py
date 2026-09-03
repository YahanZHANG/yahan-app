import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .models import GameScore


# =========================================================
# Helpers
# =========================================================

def get_display_name(user):

    try:
        profile = user.profile

    except ObjectDoesNotExist:
        return user.username

    return profile.display_name


def normalise_level(game, raw_level):

    if game == GameScore.Game.BLOCK_BREAKER:
        return 0

    if game == GameScore.Game.TAP_STAR:

        try:
            level = int(raw_level)

        except (TypeError, ValueError):
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
        .filter(user=user)
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
# Pages
# =========================================================

@login_required
def game_list(request):

    return render(
        request,
        "games/index.html",
    )


@login_required
def block_breaker(request):

    ranking = get_ranking_data(
        request.user,
        GameScore.Game.BLOCK_BREAKER,
        0,
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
# Save score API
# =========================================================

@login_required
@require_POST
def save_score(request):

    try:
        data = json.loads(
            request.body.decode("utf-8")
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

    game = data.get("game")

    if game not in GameScore.Game.values:

        return JsonResponse(
            {
                "ok": False,
                "error": "Unknown game.",
            },
            status=400,
        )

    try:
        score = int(
            data.get("score")
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
        data.get("level"),
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

    ranking = get_ranking_data(
        request.user,
        game,
        level,
    )

    return JsonResponse(
        {
            "ok": True,
            "is_new_best": is_new_best,
            "submitted_score": score,
            **ranking,
        }
    )


# =========================================================
# Ranking API
# =========================================================

@login_required
@require_GET
def ranking(request, game):

    if game not in GameScore.Game.values:

        return JsonResponse(
            {
                "ok": False,
                "error": "Unknown game.",
            },
            status=404,
        )

    level = normalise_level(
        game,
        request.GET.get("level"),
    )

    if level is None:

        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid level.",
            },
            status=400,
        )

    ranking_data = get_ranking_data(
        request.user,
        game,
        level,
    )

    return JsonResponse(
        {
            "ok": True,
            **ranking_data,
        }
    )