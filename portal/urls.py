from django.urls import path

from . import views


app_name = "portal"


urlpatterns = [

    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "setup/password/",
        views.InitialPasswordSetupView.as_view(),
        name="password_setup",
    ),

    path(
        "setup/nickname/",
        views.nickname_setup,
        name="nickname_setup",
    ),

    path(
        "setup/apps/",
        views.app_setup,
        name="app_setup",
    ),

    path(
        "apps/manage/",
        views.manage_apps,
        name="manage_apps",
    ),

]