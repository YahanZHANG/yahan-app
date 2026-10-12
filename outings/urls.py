
from django.urls import path

from . import views


app_name = "outings"


urlpatterns = [

    # =====================================================
    # HOME / Search
    # =====================================================

    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "search/",
        views.search,
        name="search",
    ),


    # =====================================================
    # Event detail / Hearts
    # =====================================================

    path(
        "event/<int:pk>/",
        views.event_detail,
        name="event_detail",
    ),

    path(
        "event/<int:pk>/heart/",
        views.toggle_heart,
        name="toggle_heart",
    ),


    # =====================================================
    # My Page
    # =====================================================

    path(
        "my/",
        views.my_page,
        name="my_page",
    ),

    # Hearted events

    path(
        "my/saved/",
        views.saved_events,
        name="saved_events",
    ),


    # =====================================================
    # Preferences
    # =====================================================

    # Display preferences page (GET)

    path(
        "my/preferences/",
        views.my_preferences,
        name="my_preferences",
    ),

    # Save preferences (POST)

    path(
        "my/preferences/save/",
        views.save_preferences,
        name="save_preferences",
    ),


    # =====================================================
    # Notifications
    # =====================================================

    path(
        "my/notifications/",
        views.my_notifications,
        name="my_notifications",
    ),

    path(
        "my/notifications/<int:pk>/open/",
        views.notification_open,
        name="notification_open",
    ),


    # =====================================================
    # Event submissions
    # =====================================================

    path(
        "post/new/",
        views.event_create,
        name="event_create",
    ),

    path(
        "my/posts/",
        views.my_posts,
        name="my_posts",
    ),

    path(
        "post/<int:pk>/edit/",
        views.event_edit,
        name="event_edit",
    ),

    path(
        "post/<int:pk>/delete/",
        views.event_delete,
        name="event_delete",
    ),


    # =====================================================
    # Comments
    # =====================================================

    path(
        "event/<int:pk>/comments/new/",
        views.comment_create,
        name="comment_create",
    ),

    path(
        "comments/<int:pk>/edit/",
        views.comment_edit,
        name="comment_edit",
    ),

    path(
        "comments/<int:pk>/delete/",
        views.comment_delete,
        name="comment_delete",
    ),

    path(
        "my/comments/",
        views.my_comments,
        name="my_comments",
    ),

]
