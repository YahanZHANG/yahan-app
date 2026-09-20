from django.urls import path

from . import views


app_name = "games"


urlpatterns = [

    path(
        "",
        views.game_list,
        name="game_list",
    ),

    path(
        "block-breaker/",
        views.block_breaker,
        name="block_breaker",
    ),

    path(
        "tap-star/",
        views.tap_star,
        name="tap_star",
    ),

    path(
        "maze-chase/",
        views.maze_chase,
        name="maze_chase",
    ),

    path(
        "maaario/",
        views.maaario,
        name="maaario",
    ),

    # API

    path(
        "api/score/",
        views.save_score,
        name="save_score",
    ),

    path(
        "api/ranking/<str:game>/",
        views.ranking,
        name="ranking",
    ),

]