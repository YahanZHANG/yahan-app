
from django.urls import path
from . import find_views, photo_admin, reports, saved_views, sunny, visits, views, discovery_views, event_views, search_views, spot_views


app_name = "outings"


urlpatterns = [

    path("visit/<str:target>/<int:pk>/", visits.save_visit, name="save_visit"),

    # =====================================================
    # HOME / Search
    # =====================================================

    path(
        "",
        spot_views.home,
        name="home",
    ),
    path("find/", find_views.find, name="find"),
    path(
        "events/",
        find_views.from_events,
        name="event_home",
    ),
    path(
        "spots/",
        spot_views.spot_list_redirect,
        name="spot_list",
    ),
    path(
        "spots/<int:pk>/",
        spot_views.spot_detail,
        name="spot_detail",
    ),
    path(
        "sunny/",
        find_views.from_sunny,
        name="sunny",
    ),
    path(
        "profile/",
        spot_views.profile_save,
        name="profile_save",
    ),
    path(
        "about/",
        views.about_outings,
        name="about_outings",
    ),

    path("my/saved/all/", saved_views.saved, name="saved_all"),
    path("my/family/", saved_views.family_page, name="family"),
    path("list/", find_views.browse, name="browse"),
    path("photo/<str:target>/<int:pk>/", photo_admin.staff_photo, name="staff_photo"),
    path("report/<str:target>/<int:pk>/", reports.send_report, name="send_report"),
    path(
        "search/",
        find_views.from_search,
        name="search",
    ),


    # =====================================================
    # Event detail / Hearts
    # =====================================================

    path(
        "event/<int:pk>/",
        event_views.event_detail,
        name="event_detail",
    ),

    path(
        "event/<int:pk>/calendar.ics",
        event_views.event_calendar,
        name="event_calendar",
    ),

    path(
        "event/<int:pk>/heart/",
        event_views.toggle_heart,
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

from django.urls import include

urlpatterns += [
    path(
        "trips/",
        include("outings.tourist_urls"),
    ),
]
