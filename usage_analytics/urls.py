from django.urls import path

from . import views

from . import heartbeat as heartbeat_views


app_name = "usage_analytics"


urlpatterns = [

    # =====================================================
    # Dashboard
    # =====================================================

    path(
        "",
        views.dashboard,
        name="dashboard",
    ),


    # =====================================================
    # Analytics with Graphic
    # =====================================================

    path(
        "apps/news/",
        views.news_app_detail,
        name="news_app_detail",
    ),

    path(
        "apps/news/campaigns/<slug:source>/<slug:medium>/<slug:campaign>/",
        views.news_campaign_detail,
        name="news_campaign_detail",
    ),

    # =====================================================
    # Public News detail
    # =====================================================

    path(
        "public-news/",
        views.public_news_detail,
        name="public_news_detail",
    ),
    path(
        "public-news/visitors/<uuid:visitor_id>/",
        views.public_news_visitor_detail,
        name="public_news_visitor_detail",
    ),
    path(
        "public-news/articles/<int:article_id>/click/",
        views.public_news_article_click,
        name="public_news_article_click",
    ),
    path(
        "users/<int:user_id>/news/",
        views.user_news_detail,
        name="user_news_detail",
    ),
    # =====================================================
    # Analytics filters
    # =====================================================

    path(
        "filters/",
        views.filters,
        name="filters",
    ),

    # =====================================================
    # User detail
    # =====================================================

    path(
        "users/<int:user_id>/",
        views.user_detail,
        name="user_detail",
    ),

    # =====================================================
    # Access control
    # =====================================================

    path(
        "access/",
        views.access_control,
        name="access_control",
    ),

    # =====================================================
    # Heartbeat
    # =====================================================

    path(
        "heartbeat/",
        heartbeat_views.heartbeat,
        name="heartbeat",
    ),

    # =====================================================
    # Online users
    # =====================================================

    path(
        "online/",
        heartbeat_views.online_users,
        name="online_users",
    ),

]
