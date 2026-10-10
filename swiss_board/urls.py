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
        "posts/<int:pk>/",
        views.post_detail,
        name="post_detail",
    ),

]