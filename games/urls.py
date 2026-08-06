from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    path("", views.game_list, name="game_list"),
    path(
        "block-breaker/",
        views.block_breaker,
        name="block_breaker",
    ),
]