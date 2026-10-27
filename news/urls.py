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
        "a/<int:article_id>/",
        views.article_detail,
        name="article_detail",
    ),

    path(
        "life/",
        views.life_alerts,
        name="life_alerts",
    ),

    path(
        "install/",
        views.install_guide,
        name="install",
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
        "internal/export/",
        internal_views.export_news_internal,
        name="internal_export",
    ),

    path(
        "digests/",
        views.digest_list,
        name="digest_list",
    ),

    path(
        "info/",
        views.info_bar,
        name="info_bar",
    ),

    path(
        "search/",
        views.search,
        name="search",
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
    
    path(
        "support/bitcoin/qr/",
        views.bitcoin_qr,
        name="bitcoin_qr",
    ),
]