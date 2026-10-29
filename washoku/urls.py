from django.urls import path

from . import views


app_name = "washoku"

urlpatterns = [
    path("", views.home, name="home"),

    # 探す
    path("recipes/", views.recipe_list, name="recipe_list"),
    path("mood/", views.find_by_mood, name="find_by_mood"),
    path("find/", views.find_by_ingredients, name="find_by_ingredients"),
    path("nutrition/", views.find_by_nutrition, name="find_by_nutrition"),
    path("random/", views.random_recipe, name="random_recipe"),

    # レシピ
    path("recipes/new/", views.recipe_submit, name="recipe_submit"),
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("recipes/<int:pk>/rate/", views.rate_recipe, name="rate_recipe"),
    path("recipes/<int:pk>/favorite/", views.favorite_toggle, name="favorite_toggle"),
    path("recipes/<int:pk>/note/", views.note_save, name="note_save"),

    # 食材
    path("ingredients/", views.ingredient_list, name="ingredient_list"),
    path("ingredients/<int:pk>/", views.ingredient_detail, name="ingredient_detail"),
    path("substitutes/", views.substitute_list, name="substitute_list"),
    path("substitutes/new/", views.substitute_submit, name="substitute_submit"),

    # 検索・みんなの投稿・コメント
    path("search/", views.search, name="search"),
    path("activity/", views.activity, name="activity"),

    # ホーム画面に追加する方法
    path("install/", views.install_guide, name="install"),

    # プッシュ通知
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe, name="push_unsubscribe"),
    path("push/weekly/", views.push_weekly, name="push_weekly"),
    path("push/test/", views.push_test, name="push_test"),

    # お店
    path("stores/", views.store_list, name="store_list"),
    path("stores/<int:pk>/", views.store_detail, name="store_detail"),

    # コメント・Q&A
    path("<str:target>/<int:pk>/comment/", views.comment_create, name="comment_create"),
    path("comments/<int:pk>/edit/", views.comment_edit, name="comment_edit"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    path("comments/<int:pk>/report/", views.comment_report, name="comment_report"),
    path("comments/<int:pk>/react/", views.comment_react, name="comment_react"),
    path("questions/", views.question_list, name="question_list"),
    path("questions/new/", views.question_new, name="question_new"),

    # みんなの投稿
    path("columns/", views.column_list, name="column_list"),
    path("products/", views.product_list, name="product_list"),
    path("links/", views.link_list, name="link_list"),
    path("polls/", views.poll_list, name="poll_list"),
    path("polls/suggest/", views.poll_suggest, name="poll_suggest"),
    path("posts/<int:pk>/vote/", views.poll_vote, name="poll_vote"),
    path("posts/<int:pk>/", views.post_detail, name="post_detail"),
    path("posts/<int:pk>/react/", views.post_react, name="post_react"),
    path("photos/<str:target>/<int:pk>/", views.staff_photo, name="staff_photo"),
    path("photos/add/<str:target>/<int:pk>/", views.photo_add, name="photo_add"),
    path("photos/<int:pk>/", views.photo_manage, name="photo_manage"),
    path("posts/<int:pk>/photo/", views.post_photo, name="post_photo"),
    path("posts/new/<str:kind>/", views.post_submit, name="post_submit"),
    path("me/posts/", views.my_posts, name="my_posts"),
    path("notifications/", views.notification_list, name="notification_list"),

    # このアプリについて・マイページ
    path("about/", views.about, name="about"),
    path("me/", views.my_page, name="my_page"),
    path("me/recipes/", views.my_recipes, name="my_recipes"),
    path("me/favorites/", views.my_favorites, name="my_favorites"),
    path("me/family-favorites/", views.family_favorites, name="family_favorites"),
    path("me/notes/", views.my_notes, name="my_notes"),
    path("me/comments/", views.my_comments, name="my_comments"),

    # 家族
    path("family/", views.family, name="family"),
    path("family/invite/", views.family_invite, name="family_invite"),
    path("family/invites/<int:invite_id>/", views.family_respond, name="family_respond"),
    path("family/leave/", views.family_leave, name="family_leave"),
]
