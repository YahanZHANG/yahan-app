from django.urls import path
from . import views

app_name = "portal"

urlpatterns = [

    path(
        "signup/",
        views.signup,
        name="signup",
    ),

    path(
        "signup/verify/<uidb64>/<token>/",
        views.verify_email,
        name="verify_email",
    ),

    path(
        "account/delete/",
        views.delete_account,
        name="delete_account",
    ),

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

    path(
        "apps/request-access/",
        views.request_app_access,
        name="request_app_access",
    ),
]