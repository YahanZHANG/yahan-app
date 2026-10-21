from django.urls import path
from django.views.generic import RedirectView

from . import views

from . import heartbeat as heartbeat_views


app_name = "usage_analytics"


urlpatterns = [

    # =====================================================
    # Dashboard
    # =====================================================

    path("", views.dashboard, name="dashboard"),

    path("live/", views.live_status, name="live_status"),

    # =====================================================
    # 1人ずつの足あと
    # =====================================================

    path("visitors/<uuid:visitor_id>/", views.visitor_detail, name="visitor_detail"),

    path("users/<int:user_id>/", views.user_detail, name="user_detail"),

    # =====================================================
    # Settings
    # =====================================================

    path("settings/", views.settings_view, name="settings"),

    path("settings/ignore-browser/", views.toggle_ignore_browser, name="toggle_ignore_browser"),

    path("access/", views.access_control, name="access_control"),

    # =====================================================
    # Swiss News article click (記録してから元記事へ)
    # =====================================================

    path(
        "public-news/articles/<int:article_id>/click/",
        views.public_news_article_click,
        name="public_news_article_click",
    ),

    # =====================================================
    # Old URLs (前の解析ページ)
    # =====================================================

    path("apps/news/", views.legacy_redirect),

    path("apps/news/campaigns/<slug:source>/<slug:medium>/<slug:campaign>/", views.legacy_redirect),

    path("public-news/", views.legacy_redirect),

    path("public-news/visitors/<uuid:visitor_id>/", views.legacy_redirect),

    path("users/<int:user_id>/news/", views.legacy_redirect),

    path("filters/", RedirectView.as_view(pattern_name="usage_analytics:settings")),

    # =====================================================
    # Heartbeat
    # =====================================================

    path("heartbeat/", heartbeat_views.heartbeat, name="heartbeat"),

    path("online/", heartbeat_views.online_users, name="online_users"),

]
