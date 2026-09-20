from django.urls import path

from . import views


app_name = "board"


urlpatterns = [

    # 掲示板一覧
    path(
        "",
        views.post_list,
        name="post_list",
    ),

    # 新規投稿
    path(
        "new/",
        views.post_create,
        name="post_create",
    ),

    # 投稿詳細
    path(
        "<int:pk>/",
        views.post_detail,
        name="post_detail",
    ),

    # 投稿編集
    path(
        "<int:pk>/edit/",
        views.post_edit,
        name="post_edit",
    ),

    # 投稿削除
    path(
        "<int:pk>/delete/",
        views.post_delete,
        name="post_delete",
    ),

    # コメント削除
    path(
        "comments/<int:pk>/delete/",
        views.comment_delete,
        name="comment_delete",
    ),

]