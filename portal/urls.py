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
        "setup/password/",
        views.InitialPasswordSetupView.as_view(),
        name="password_setup",
    ),

]