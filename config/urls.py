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

            # ログイン後は、アクセス元ではなく
            # 必ずポータルへ戻す
            redirect_field_name=None,
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
]