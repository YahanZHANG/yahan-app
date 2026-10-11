
from django.urls import path
from . import views

app_name = "outings"

urlpatterns = [
    path(
        "",
        views.home,
        name="home",
    ),
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
    path(
        "my/",
        views.my_page,
        name="my_page",
    ),
    path(
        "my/preferences/",
        views.save_preferences,
        name="save_preferences",
    ),

    
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

]
