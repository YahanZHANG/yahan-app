from django.urls import path

from . import views


app_name = "washoku"

urlpatterns = [
    path("", views.home, name="home"),

    # 探す
    path("recipes/", views.recipe_list, name="recipe_list"),
    path("mood/", views.find_by_mood, name="find_by_mood"),
    path("find/", views.find_by_ingredients, name="find_by_ingredients"),
    path("random/", views.random_recipe, name="random_recipe"),

    # レシピ
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("recipes/<int:pk>/rate/", views.rate_recipe, name="rate_recipe"),

    # 食材
    path("ingredients/", views.ingredient_list, name="ingredient_list"),
    path("ingredients/<int:pk>/", views.ingredient_detail, name="ingredient_detail"),

    # お店
    path("stores/", views.store_list, name="store_list"),
    path("stores/<int:pk>/", views.store_detail, name="store_detail"),

    # コメント・Q&A
    path("<str:target>/<int:pk>/comment/", views.comment_create, name="comment_create"),
    path("comments/<int:pk>/edit/", views.comment_edit, name="comment_edit"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    path("comments/<int:pk>/report/", views.comment_report, name="comment_report"),
    path("questions/", views.question_list, name="question_list"),
    path("notifications/", views.notification_list, name="notification_list"),

    # このアプリについて・マイページ
    path("about/", views.about, name="about"),
    path("me/", views.my_page, name="my_page"),
    path("me/favorites/", views.my_favorites, name="my_favorites"),
    path("me/comments/", views.my_comments, name="my_comments"),

    # 家族
    path("family/", views.family, name="family"),
    path("family/invite/", views.family_invite, name="family_invite"),
    path("family/invites/<int:invite_id>/", views.family_respond, name="family_respond"),
    path("family/leave/", views.family_leave, name="family_leave"),
]
