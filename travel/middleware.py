from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import resolve, reverse

from .models import AppAccessRequest


# =========================================================
# Travel management access
# =========================================================

class TravelAccessMiddleware:
    """
    travel_usersグループの利用者と管理者だけ、
    旅行管理アプリへアクセスできるようにする。
    """

    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):

        if not request.path.startswith("/travel/"):
            return self.get_response(request)


        if not request.user.is_authenticated:

            login_url = reverse("login")

            query_string = urlencode(
                {
                    "next": request.get_full_path(),
                }
            )

            return redirect(
                f"{login_url}?{query_string}"
            )


        can_use_travel = (
            request.user.is_superuser
            or request.user.groups.filter(
                name="travel_users"
            ).exists()
        )


        if not can_use_travel:

            messages.error(
                request,
                "このアカウントでは旅行管理アプリを利用できません。",
            )

            return redirect(
                "portal:home"
            )


        return self.get_response(request)


# =========================================================
# Public signup user access
# =========================================================

PUBLIC_USER_GROUP = "public_users"


ALLOWED_NAMESPACES = {
    "portal",
    "news",
    "recipes",
    "colorcheck",
    "event_scheduler",
}


ALLOWED_VIEW_NAMES = {
    "login",
    "logout",

    "password_change",
    "password_change_done",

    "password_reset",
    "password_reset_done",
    "password_reset_confirm",
    "password_reset_complete",

    "pwa_manifest",
    "pwa_service_worker",

    "news_push_settings",
    "news_push_subscribe",
    "news_push_unsubscribe",
}


REQUESTABLE_APPS = {

    "feeding": {
        "key": "feeding",
        "name": "離乳食記録",
    },

    "vaccination": {
        "key": "vaccination",
        "name": "ワクチン記録",
    },

    "games": {
        "key": "games",
        "name": "ミニゲーム",
    },

    "chat": {
        "key": "chat",
        "name": "チャット",
    },

    "board": {
        "key": "board",
        "name": "掲示板",
    },

}


class PublicUserAccessMiddleware:
    """
    public_usersグループのユーザーが、
    一般公開対象外のアプリへアクセスすることを制限する。

    管理者が個別承認したアプリは利用可能。
    """

    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):

        user = request.user


        # ---------------------------------------------
        # Anonymous
        # ---------------------------------------------

        if not user.is_authenticated:
            return self.get_response(request)


        # ---------------------------------------------
        # Superuser
        # ---------------------------------------------

        if user.is_superuser:
            return self.get_response(request)


        # ---------------------------------------------
        # Existing private users
        # ---------------------------------------------

        is_public_user = (
            user.groups.filter(
                name=PUBLIC_USER_GROUP
            ).exists()
        )

        if not is_public_user:
            return self.get_response(request)


        # ---------------------------------------------
        # Static / media
        # ---------------------------------------------

        if (
            request.path.startswith("/static/")
            or request.path.startswith("/media/")
        ):
            return self.get_response(request)


        # ---------------------------------------------
        # Resolve URL
        # ---------------------------------------------

        try:

            match = resolve(
                request.path_info
            )

        except Exception:

            return self.get_response(request)


        namespace = match.namespace
        view_name = match.view_name

        # ---------------------------------------------
        # Publicly available apps
        # ---------------------------------------------

        if namespace in ALLOWED_NAMESPACES:
            return self.get_response(request)


        if view_name in ALLOWED_VIEW_NAMES:
            return self.get_response(request)


        # ---------------------------------------------
        # Identify requested private app
        # ---------------------------------------------

        requested_app = (
            REQUESTABLE_APPS.get(
                namespace
            )
        )


        # Namespaceが取れない場合にURLから判定
        if not requested_app:

            path_map = {

                "/feeding/": {
                    "key": "feeding",
                    "name": "離乳食記録",
                },

                "/vaccination/": {
                    "key": "vaccination",
                    "name": "ワクチン記録",
                },

                "/games/": {
                    "key": "games",
                    "name": "ミニゲーム",
                },

                "/chat/": {
                    "key": "chat",
                    "name": "チャット",
                },

                "/board/": {
                    "key": "board",
                    "name": "掲示板",
                },

            }


            for prefix, app_info in path_map.items():

                if request.path.startswith(
                    prefix
                ):

                    requested_app = app_info

                    break


        # ---------------------------------------------
        # Existing access request
        # ---------------------------------------------

        access_request = None


        if requested_app:

            access_request = (
                AppAccessRequest.objects
                .filter(
                    user=user,
                    app_key=requested_app["key"],
                )
                .first()
            )


            # Approved -> allow
            if (
                access_request
                and access_request.status
                == AppAccessRequest.Status.APPROVED
            ):

                return self.get_response(
                    request
                )


        # ---------------------------------------------
        # Denied
        # ---------------------------------------------

        return render(
            request,
            "portal/access_denied.html",
            {
                "requested_app": requested_app,
                "requested_path": request.path,
                "access_request": access_request,
            },
            status=403,
        )