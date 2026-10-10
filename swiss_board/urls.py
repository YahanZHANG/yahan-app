from django.urls import path

from . import views


app_name = "swiss_board"


urlpatterns = [

    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "search/",
        views.post_search,
        name="search",
    ),

    path(
        "categories/",
        views.category_menu,
        name="categories",
    ),

    path(
        "mypage/",
        views.my_page,
        name="my_page",
    ),

    path(
        "mypage/profile/",
        views.profile_edit,
        name="profile_edit",
    ),

    path(
        "my-posts/",
        views.my_posts,
        name="my_posts",
    ),

    path(
        "posts/new/",
        views.post_create,
        name="post_create",
    ),

    path(
        "posts/<int:pk>/edit/",
        views.post_edit,
        name="post_edit",
    ),

    path(
        "posts/<int:pk>/delete/",
        views.post_delete,
        name="post_delete",
    ),

    path(
        "posts/<int:pk>/",
        views.post_detail,
        name="post_detail",
    ),

]