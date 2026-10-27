from django.urls import path
from . import support_views, views

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
        "signup/resend-verification/",
        views.resend_verification,
        name="resend_verification",
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
        "ideas/",
        views.send_app_idea,
        name="send_app_idea",
    ),
    path(
        "support/",
        support_views.support,
        name="support",
    ),
    path(
        "help/",
        support_views.help_page,
        name="help",
    ),
    path(
        "support/<str:method>/",
        support_views.support_contact,
        name="support_contact",
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