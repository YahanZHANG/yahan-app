import logging

from django.db import DatabaseError
from django.utils import timezone

from .models import UsageEvent


logger = logging.getLogger(__name__)


# =========================================================
# Tracking settings
# =========================================================

VISIT_TIMEOUT_SECONDS = 30 * 60

SESSION_KEY = "usage_analytics_last_seen"


APP_PATHS = {

    "/news": "news",

    "/feeding": "feeding",

    "/vaccination": "vaccination",

    "/recipes": "recipes",

    "/games": "games",

    "/colorcheck": "colorcheck",

}


PORTAL_PATHS = {
    "/",
    "/apps/manage/",
}


# =========================================================
# Helpers
# =========================================================

def get_app_key(path):

    if path in PORTAL_PATHS:
        return "portal"

    for prefix, app_key in APP_PATHS.items():

        if (
            path == prefix
            or path.startswith(
                prefix + "/"
            )
        ):
            return app_key

    return None


# =========================================================
# Middleware
# =========================================================

class UsageAnalyticsMiddleware:

    def __init__(self, get_response):

        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(
            request
        )

        # ---------------------------------------------
        # Only authenticated users
        # ---------------------------------------------

        if not request.user.is_authenticated:
            return response

        # ---------------------------------------------
        # Only GET requests
        # ---------------------------------------------

        if request.method != "GET":
            return response

        # ---------------------------------------------
        # Only successful HTML responses
        # ---------------------------------------------

        if not (
            200 <= response.status_code < 300
        ):
            return response

        content_type = response.get(
            "Content-Type",
            "",
        )

        if not content_type.startswith(
            "text/html"
        ):
            return response

        # ---------------------------------------------
        # Identify app
        # ---------------------------------------------

        app_key = get_app_key(
            request.path_info
        )

        if app_key is None:
            return response

        # ---------------------------------------------
        # Session tracking
        # ---------------------------------------------

        now = timezone.now()

        now_timestamp = now.timestamp()

        last_seen_map = (
            request.session.get(
                SESSION_KEY,
                {},
            )
        )

        session_app_key = (
            f"{request.user.pk}:{app_key}"
        )

        last_timestamp = (
            last_seen_map.get(
                session_app_key
            )
        )

        is_visit_start = (
            last_timestamp is None
            or (
                now_timestamp
                - last_timestamp
            ) > VISIT_TIMEOUT_SECONDS
        )

        # ---------------------------------------------
        # Save usage event
        # ---------------------------------------------

        try:

            UsageEvent.objects.create(

                user=request.user,

                app_key=app_key,

                is_visit_start=(
                    is_visit_start
                ),

            )

        except DatabaseError:

            logger.exception(
                "Failed to save usage event."
            )

            # Analytics failure should not
            # prevent normal app usage.

            return response

        # ---------------------------------------------
        # Update session
        # ---------------------------------------------

        last_seen_map = dict(
            last_seen_map
        )

        last_seen_map[
            session_app_key
        ] = now_timestamp

        request.session[
            SESSION_KEY
        ] = last_seen_map

        return response