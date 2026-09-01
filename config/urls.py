from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
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
]