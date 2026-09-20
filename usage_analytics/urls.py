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
