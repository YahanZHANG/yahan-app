import logging
import uuid

from urllib.parse import urlparse

from django.conf import settings
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


PUBLIC_NEWS_VISITOR_COOKIE = (
    "yahan_news_visitor_id"
)


PUBLIC_NEWS_VISITOR_COOKIE_MAX_AGE = (
    60 * 60 * 24 * 365
)


PUBLIC_NEWS_VISIT_ID_SESSION_KEY = (
    "public_news_visit_id"
)


PUBLIC_NEWS_LAST_SEEN_SESSION_KEY = (
    "public_news_last_seen"
)


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


def normalize_uuid(value):

    if not value:
        return None

    try:

        return str(
            uuid.UUID(
                str(value)
            )
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
    ):

        return None


def get_public_news_visitor(
    request,
):

    # -----------------------------------------------------
    # New long-term cookie
    # -----------------------------------------------------

    visitor_id = normalize_uuid(
        request.COOKIES.get(
            PUBLIC_NEWS_VISITOR_COOKIE
        )
    )

    if visitor_id:

        request.session[
            "public_news_visitor_id"
        ] = visitor_id

        return (
            visitor_id,
            False,
            False,
        )


    # -----------------------------------------------------
    # Preserve old visitor IDs already stored in session
    # -----------------------------------------------------

    legacy_visitor_id = normalize_uuid(
        request.session.get(
            "public_news_visitor_id"
        )
    )


    if legacy_visitor_id:

        visitor_id = legacy_visitor_id

    else:

        visitor_id = str(
            uuid.uuid4()
        )


    # -----------------------------------------------------
    # Is this truly the first visit we have ever recorded?
    # -----------------------------------------------------

    is_new_visitor = not (
        PublicNewsEvent.objects.filter(
            visitor_id=visitor_id
        ).exists()
    )


    request.session[
        "public_news_visitor_id"
    ] = visitor_id


    return (
        visitor_id,
        True,
        is_new_visitor,
    )


def set_public_news_visitor_cookie(
    response,
    visitor_id,
):

    response.set_cookie(

        key=PUBLIC_NEWS_VISITOR_COOKIE,

        value=str(visitor_id),

        max_age=(
            PUBLIC_NEWS_VISITOR_COOKIE_MAX_AGE
        ),

        httponly=True,

        secure=not settings.DEBUG,

        samesite="Lax",

    )


def get_public_news_visit(
    request,
    now_timestamp=None,
):

    if now_timestamp is None:

        now_timestamp = (
            timezone.now().timestamp()
        )


    last_timestamp = request.session.get(
        PUBLIC_NEWS_LAST_SEEN_SESSION_KEY
    )


    visit_id = normalize_uuid(
        request.session.get(
            PUBLIC_NEWS_VISIT_ID_SESSION_KEY
        )
    )


    is_visit_start = (

        visit_id is None

        or last_timestamp is None

        or (
            now_timestamp
            - float(last_timestamp)
        ) > VISIT_TIMEOUT_SECONDS

    )


    if is_visit_start:

        visit_id = str(
            uuid.uuid4()
        )


    request.session[
        PUBLIC_NEWS_VISIT_ID_SESSION_KEY
    ] = visit_id


    request.session[
        PUBLIC_NEWS_LAST_SEEN_SESSION_KEY
    ] = now_timestamp


    return (
        visit_id,
        is_visit_start,
    )


def get_device_type(request):

    user_agent = (
        request.META.get(
            "HTTP_USER_AGENT",
            "",
        )
        .lower()
    )


    tablet_keywords = (
        "ipad",
        "tablet",
        "kindle",
    )


    if any(
        keyword in user_agent
        for keyword in tablet_keywords
    ):

        return "tablet"


    mobile_keywords = (
        "iphone",
        "android",
        "mobile",
    )


    if any(
        keyword in user_agent
        for keyword in mobile_keywords
    ):

        return "mobile"


    if user_agent:

        return "desktop"


    return "other"


def get_referrer_host(request):

    referrer = request.META.get(
        "HTTP_REFERER",
        "",
    )


    if not referrer:
        return ""


    try:

        hostname = (
            urlparse(
                referrer
            ).hostname
            or ""
        )

    except ValueError:

        return ""


    return hostname[:255]


def clean_tracking_value(
    value,
    max_length,
):

    if not value:
        return ""

    return str(value)[:max_length]


# =========================================================
# Middleware
# =========================================================


class UsageAnalyticsMiddleware:

    def __init__(
        self,
        get_response,
    ):

        self.get_response = (
            get_response
        )


    def __call__(
        self,
        request,
    ):

        response = self.get_response(
            request
        )


        # -------------------------------------------------
        # Only GET
        # -------------------------------------------------

        if request.method != "GET":
            return response


        # -------------------------------------------------
        # Successful HTML only
        # -------------------------------------------------

        if not (
            200
            <= response.status_code
            < 300
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


        # -------------------------------------------------
        # Public Swiss News
        # -------------------------------------------------

        if (
            not request.user.is_authenticated
            and (
                request.path_info == "/news"
                or request.path_info.startswith(
                    "/news/"
                )
            )
        ):

            visitor_id = (
                self._track_public_news(
                    request
                )
            )


            if visitor_id:

                set_public_news_visitor_cookie(
                    response,
                    visitor_id,
                )


            return response


        # -------------------------------------------------
        # Authenticated only from here
        # -------------------------------------------------

        if not request.user.is_authenticated:
            return response


        app_key = get_app_key(
            request.path_info
        )


        if app_key is None:
            return response


        now = timezone.now()

        now_timestamp = (
            now.timestamp()
        )


        # -------------------------------------------------
        # Detailed News
        # -------------------------------------------------

        if app_key == "news":

            self._track_authenticated_news(

                request=request,

                now_timestamp=(
                    now_timestamp
                ),

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


    # =====================================================
    # Public News
    # =====================================================

    def _track_public_news(
        self,
        request,
    ):

        now = timezone.now()

        now_timestamp = (
            now.timestamp()
        )


        (
            visitor_id,
            should_set_cookie,
            is_new_visitor,
        ) = get_public_news_visitor(
            request
        )


        (
            visit_id,
            is_visit_start,
        ) = get_public_news_visit(

            request,

            now_timestamp=(
                now_timestamp
            ),

        )


        referrer_host = ""

        utm_source = ""

        utm_medium = ""

        utm_campaign = ""


        # Acquisition information only needs to be attached
        # to the first page of each visit.

        if is_visit_start:

            referrer_host = (
                get_referrer_host(
                    request
                )
            )


            utm_source = (
                clean_tracking_value(
                    request.GET.get(
                        "utm_source"
                    ),
                    100,
                )
            )


            utm_medium = (
                clean_tracking_value(
                    request.GET.get(
                        "utm_medium"
                    ),
                    100,
                )
            )


            utm_campaign = (
                clean_tracking_value(
                    request.GET.get(
                        "utm_campaign"
                    ),
                    150,
                )
            )


        try:

            PublicNewsEvent.objects.create(

                visitor_id=visitor_id,

                visit_id=visit_id,

                path=request.path_info,

                is_visit_start=(
                    is_visit_start
                ),

                is_new_visitor=(
                    is_new_visitor
                ),

                referrer_host=(
                    referrer_host
                ),

                utm_source=(
                    utm_source
                ),

                utm_medium=(
                    utm_medium
                ),

                utm_campaign=(
                    utm_campaign
                ),

                device_type=(
                    get_device_type(
                        request
                    )
                ),

            )

        except DatabaseError:

            logger.exception(
                "Failed to save public news event."
            )

            return None


        if should_set_cookie:

            return visitor_id


        return None


    # =====================================================
    # Authenticated News
    # =====================================================

    def _track_authenticated_news(
        self,
        request,
        now_timestamp,
    ):

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


        try:

            UserNewsEvent.objects.create(

                user=request.user,

                path=request.path_info,

                is_visit_start=(
                    is_visit_start
                ),

            )

        except DatabaseError:

            logger.exception(
                "Failed to save "
                "authenticated news event."
            )

            return


        request.session[
            session_key
        ] = now_timestamp