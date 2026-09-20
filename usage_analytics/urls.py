from django.urls import path

from . import views


app_name = "usage_analytics"


urlpatterns = [

    path(
        "",
        views.dashboard,
        name="dashboard",
    ),

    path(
        "users/<int:user_id>/",
        views.user_detail,
        name="user_detail",
    ),

    path(
        "access/",
        views.access_control,
        name="access_control",
    ),

]