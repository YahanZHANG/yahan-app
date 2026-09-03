from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="/password/change/done/",
        ),
        name="password_change",
    ),

    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(
            next_page="/accounts/login/",
        ),
        name="logout",
    ),

    path(
        "",
        include("portal.urls"),
    ),

    path(
        "travel/",
        include(
            "travel.urls",
            namespace="travel",
        ),
    ),

    path(
        "feeding/",
        include(
            "feeding.urls",
            namespace="feeding",
        ),
    ),

    path(
        "games/",
        include(
            "games.urls",
            namespace="games",
        ),
    ),

    path(
        "vaccination/",
        include(
            "vaccination.urls",
            namespace="vaccination",
        ),
    ),

    path(
        "colorcheck/", 
        include(
            "colorcheck.urls",
            namespace="colorcheck",
        ),
    ),

    path(
        "recipes/", 
        include(
            "recipes.urls",
            namespace="recipes",
        ),
    ),
]