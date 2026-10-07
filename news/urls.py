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
        "about/",
        views.about,
        name="about",
    ),

    path(
        "services/",
        views.services,
        name="services",
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

    path(
        "digests/",
        views.digest_list,
        name="digest_list",
    ),

    path(
        "sources/<int:source_id>/",
        views.source_detail,
        name="source_detail",
    ),

    path(
        "regions/<slug:slug>/",
        views.region_detail,
        name="region_detail",
    ),

    path(
        "support/<str:method>/",
        views.support_contact,
        name="support_contact",
    ),
]