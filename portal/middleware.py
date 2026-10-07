from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import resolve

from portal.models import AppAccessRequest


PUBLIC_USER_GROUP = "public_users"

REQUESTABLE_APPS = {

    "feeding": {
        "key": "feeding",
        "name": "離乳食記録",
    },

    "vaccination": {
        "key": "vaccination",
        "name": "ワクチン記録",
    },


    "chat": {
        "key": "chat",
        "name": "チャット",
    },

}

# =========================================================
# Apps available to public signup users
# =========================================================

ALLOWED_NAMESPACES = {
    "portal",
    "news",
    "recipes",
    "colorcheck",
    "event_scheduler",
    "board",
    "games",
}


# Namespaceを持たないが利用を許可するURL
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


class PublicUserAccessMiddleware:
    """
    public_users グループのユーザーが、
    一般公開対象外のアプリへアクセスすることを防ぐ。
    """

    def __init__(
        self,
        get_response,
    ):

        self.get_response = get_response


    def __call__(
        self,
        request,
    ):

        user = request.user


        # ---------------------------------------------
        # Anonymous user
        # ---------------------------------------------

        if not user.is_authenticated:

            return self.get_response(
                request
            )


        # ---------------------------------------------
        # Admin
        # ---------------------------------------------

        if user.is_superuser:

            return self.get_response(
                request
            )


        # ---------------------------------------------
        # Existing / private users
        # ---------------------------------------------

        is_public_user = (
            user.groups.filter(
                name=PUBLIC_USER_GROUP
            ).exists()
        )

        if not is_public_user:

            return self.get_response(
                request
            )


        # ---------------------------------------------
        # Static / media
        # ---------------------------------------------

        if (
            request.path.startswith("/static/")
            or request.path.startswith("/media/")
        ):

            return self.get_response(
                request
            )


        # ---------------------------------------------
        # Resolve current URL
        # ---------------------------------------------

        try:

            match = resolve(
                request.path_info
            )

        except Exception:

            return self.get_response(
                request
            )


        namespace = match.namespace
        view_name = match.view_name
        url_name = match.url_name


        # =========================================================
        # Maaario is not available to public signup users
        # =========================================================

        if (
            namespace == "games"
            and url_name == "maaario"
        ):

            messages.info(
                request,
                "マアアアリオは現在、一般公開していません。",
            )

            return redirect(
                "games:game_list"
            )


        # ---------------------------------------------
        # Allowed namespaces
        # ---------------------------------------------

        if namespace in ALLOWED_NAMESPACES:

            return self.get_response(
                request
            )   


        # ---------------------------------------------
        # Allowed standalone views
        # ---------------------------------------------

        if view_name in ALLOWED_VIEW_NAMES:

            return self.get_response(
                request
            )


        # ---------------------------------------------
        # Denied
        # ---------------------------------------------

        requested_app = (
            REQUESTABLE_APPS.get(
                namespace
            )
        )


        # =========================================================
        # Fallback: URL path
        # =========================================================

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

                "/chat/": {
                    "key": "chat",
                    "name": "チャット",
                },
            }


            for prefix, app_info in path_map.items():

                if request.path.startswith(
                    prefix
                ):

                    requested_app = app_info

                    break


        # =========================================================
        # Approved access
        # =========================================================

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


            # ---------------------------------------------
            # Approved
            # ---------------------------------------------

            if (
                access_request
                and access_request.status
                == AppAccessRequest.Status.APPROVED
            ):

                return self.get_response(
                    request
                )

        # =========================================================
        # Denied
        # =========================================================

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