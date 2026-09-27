import logging
import uuid

from django.db import DatabaseError
from django.utils import timezone

from .models import (
    PublicNewsEvent,
    UsageEvent,
    UserNewsEvent,
)

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
        # Public News analytics
        # ---------------------------------------------

        if (
            not request.user.is_authenticated
            and (
                request.path_info == "/news"
                or request.path_info.startswith(
                    "/news/"
                )
            )
        ):

            self._track_public_news(
                request
            )

            return response

        # ---------------------------------------------
        # Existing analytics:
        # authenticated users only
        # ---------------------------------------------

        if not request.user.is_authenticated:
            return response

        app_key = get_app_key(
            request.path_info
        )

        if app_key is None:
            return response

        now = timezone.now()

        now_timestamp = now.timestamp()

        # ---------------------------------------------
        # Authenticated News detailed analytics
        # ---------------------------------------------

        if app_key == "news":

            self._track_authenticated_news(
                request=request,
                now_timestamp=now_timestamp,
            )

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

            return response

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

    
    def _track_public_news(
        self,
        request,
    ):

        now = timezone.now()

        now_timestamp = now.timestamp()

        # ---------------------------------------------
        # Anonymous visitor ID
        # ---------------------------------------------

        visitor_id = request.session.get(
            "public_news_visitor_id"
        )

        if visitor_id is None:

            visitor_id = str(
                uuid.uuid4()
            )

            request.session[
                "public_news_visitor_id"
            ] = visitor_id

        # ---------------------------------------------
        # Visit detection
        # ---------------------------------------------

        last_timestamp = (
            request.session.get(
                "public_news_last_seen"
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
        # Save event
        # ---------------------------------------------

        try:

            PublicNewsEvent.objects.create(

                visitor_id=visitor_id,

                path=request.path_info,

                is_visit_start=(
                    is_visit_start
                ),

            )

        except DatabaseError:

            logger.exception(
                "Failed to save public news event."
            )

            return

        request.session[
            "public_news_last_seen"
        ] = now_timestamp

    def _track_authenticated_news(
            self,
            request,
            now_timestamp,
        ):
            """
            ログインユーザーのSwiss News内での
            詳細なページ閲覧を記録する。
            """
    
            # ---------------------------------------------
            # Visit detection
            # ---------------------------------------------
    
            session_key = (
                f"authenticated_news_last_seen:"
                f"{request.user.pk}"
            )
    
            last_timestamp = (
                request.session.get(
                    session_key
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
            # Save event
            # ---------------------------------------------
    
            try:
    
                UserNewsEvent.objects.create(
                    user=request.user,
                    path=request.path_info,
                    is_visit_start=is_visit_start,
                )
    
            except DatabaseError:
    
                logger.exception(
                    "Failed to save authenticated news event."
                )
    
                return
    
            request.session[
                session_key
            ] = now_timestamp
    
    