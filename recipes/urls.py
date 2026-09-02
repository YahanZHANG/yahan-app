from django.urls import path

from . import views


app_name = "recipes"


urlpatterns = [
    path("", views.home, name="home"),

    path(
        "hotcook/",
        views.recipe_list,
        {"appliance_type": "hotcook"},
        name="hotcook_list",
    ),

    path(
        "chefdrum/",
        views.recipe_list,
        {"appliance_type": "chefdrum"},
        name="chefdrum_list",
    ),

    path(
        "<int:pk>/preference/",
        views.toggle_preference,
        name="toggle_preference",
    ),

    path(
        "<int:pk>/",
        views.recipe_detail,
        name="detail",
    ),

    path(
        "my-recipes/",
        views.my_recipes,
        name="my_recipes",
    ),

    path(
        "find/ingredients/",
        views.find_by_ingredients,
        name="find_by_ingredients",
    ),

    path(
        "find/mood/",
        views.find_by_mood,
        name="find_by_mood",
    ),

    path(
        "find/nutrition/",
        views.find_by_nutrition,
        name="find_by_nutrition",
    ),
]