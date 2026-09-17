from django.urls import path

from . import views
from . import internal_views


app_name = "news"


urlpatterns = [
    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "topics/",
        views.topic_list,
        name="topic_list",
    ),

    path(
        "topics/<slug:slug>/",
        views.topic_detail,
        name="topic_detail",
    ),

    path(
        "favorites/",
        views.favorites,
        name="favorites",
    ),

    path(
        "settings/",
        views.settings_view,
        name="settings",
    ),

    path(
        "favorite/<int:article_id>/toggle/",
        views.toggle_favorite,
        name="toggle_favorite",
    ),

    path(
        "internal/refresh/",
        internal_views.refresh_news_internal,
        name="internal_refresh",
    ),
]