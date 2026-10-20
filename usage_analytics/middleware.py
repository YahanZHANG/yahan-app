import logging
import re
import uuid

from urllib.parse import urlparse

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from .catalog import app_for_path, should_track_path
from .models import PageView
from .sources import classify_source


logger = logging.getLogger(__name__)


# =========================================================
# Tracking settings
# =========================================================

VISIT_TIMEOUT_SECONDS = 30 * 60

# 名前は以前の Swiss News 用のまま (今までの訪問者IDを引き継ぐため)
VISITOR_COOKIE = "yahan_news_visitor_id"

VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2

LEGACY_VISITOR_SESSION_KEY = "public_news_visitor_id"

VISIT_COOKIE = "yapp_visit"

# 解析ページの設定から「このブラウザを集計しない」を選ぶと付く
IGNORE_COOKIE = "yapp_analytics_ignore"

BOT_PATTERN = re.compile(
    r"bot|crawl|spider|slurp|scrap|preview|facebookexternalhit|"
    r"whatsapp/|headless|lighthouse|pagespeed|monitor|uptime|pingdom|"
    r"curl|wget|python|httpx|aiohttp|go-http|axios|node-fetch|okhttp|"
    r"java/|libwww|ahrefs|semrush|mj12|petal|bytespider|gptbot|"
    r"render/health",
    re.IGNORECASE,
)


# =========================================================
# Helpers
# =========================================================

def normalize_uuid(value):

    if not value:
        return None

    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def is_bot(request):

    user_agent = request.META.get("HTTP_USER_AGENT", "")

    return not user_agent or bool(BOT_PATTERN.search(user_agent))


def is_prefetch(request):

    purpose = (
        request.META.get("HTTP_SEC_PURPOSE", "")
        or request.META.get("HTTP_PURPOSE", "")
        or request.META.get("HTTP_X_PURPOSE", "")
    )

    return "prefetch" in purpose.lower()


def get_device_type(request):

    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()

    if any(word in user_agent for word in ("ipad", "tablet", "kindle")):
        return "tablet"

    if any(word in user_agent for word in ("iphone", "android", "mobile")):
        return "mobile"

    if user_agent:
        return "desktop"

    return "other"


def get_referrer_host(request):

    referrer = request.META.get("HTTP_REFERER", "")

    if not referrer:
        return ""

    try:
        hostname = urlparse(referrer).hostname or ""
    except ValueError:
        return ""

    return hostname[:255]


def clean_tracking_value(value, max_length):

    if not value:
        return ""

    return str(value)[:max_length]


def get_visitor_id(request):
    """
    (visitor_id, cookieを新しく付けるか) を返す。
    """

    visitor_id = normalize_uuid(request.COOKIES.get(VISITOR_COOKIE))

    if visitor_id:
        return visitor_id, False

    # 以前は session に入れていた
    visitor_id = normalize_uuid(
        request.session.get(LEGACY_VISITOR_SESSION_KEY)
    )

    return visitor_id or str(uuid.uuid4()), True


def get_visit(request, now_timestamp):
    """
    (visit_id, 新しい訪問か) を返す。cookie に「訪問ID.最後の時刻」を持つ。
    """

    raw = request.COOKIES.get(VISIT_COOKIE, "")
    visit_id, _, last_timestamp = raw.partition(".")
    visit_id = normalize_uuid(visit_id)

    try:
        last_timestamp = float(last_timestamp)
    except ValueError:
        last_timestamp = None

    if (
        visit_id
        and last_timestamp is not None
        and now_timestamp - last_timestamp <= VISIT_TIMEOUT_SECONDS
    ):
        return visit_id, False

    return str(uuid.uuid4()), True


def visitor_of(request):
    """記事クリックなど、他の記録から今の訪問者・訪問IDを参照する用。"""

    visitor_id = normalize_uuid(request.COOKIES.get(VISITOR_COOKIE)) or normalize_uuid(
        request.session.get(LEGACY_VISITOR_SESSION_KEY)
    )

    visit_id = normalize_uuid(
        request.COOKIES.get(VISIT_COOKIE, "").partition(".")[0]
    )

    return visitor_id, visit_id


def own_hosts(request):

    return {request.get_host().split(":", 1)[0].lower()}


# =========================================================
# Middleware
# =========================================================

class UsageAnalyticsMiddleware:
    """
    全アプリのページ閲覧を PageView に1行ずつ記録する。

    記録するのは、成功した GET の HTML ページだけ。
    bot・先読み・解析ページ自身・管理画面は記録しない。
    """

    def __init__(self, get_response):

        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        if not self._should_track(request, response):
            return response

        now = timezone.now()
        now_timestamp = now.timestamp()

        visitor_id, is_new_cookie = get_visitor_id(request)
        visit_id, is_visit_start = get_visit(request, now_timestamp)

        user = request.user if request.user.is_authenticated else None

        page_view = PageView(
            visitor_id=visitor_id,
            visit_id=visit_id,
            user=user,
            app_key=app_for_path(request.path_info),
            path=request.path_info[:300],
            accessed_at=now,
            is_visit_start=is_visit_start,
            device_type=get_device_type(request),
        )

        if is_new_cookie:
            page_view.is_new_visitor = not self._seen_before(visitor_id, user)

        # 流入元は訪問の最初のページにだけ付ける
        if is_visit_start:
            page_view.referrer_host = get_referrer_host(request)
            page_view.utm_source = clean_tracking_value(request.GET.get("utm_source"), 100)
            page_view.utm_medium = clean_tracking_value(request.GET.get("utm_medium"), 100)
            page_view.utm_campaign = clean_tracking_value(request.GET.get("utm_campaign"), 150)
            page_view.source_type, page_view.source_label = classify_source(
                page_view.referrer_host,
                page_view.utm_source,
                own_hosts(request),
            )

        try:
            page_view.save()
        except DatabaseError:
            logger.exception("Failed to save page view.")
            return response

        secure = not settings.DEBUG

        if is_new_cookie:
            response.set_cookie(
                VISITOR_COOKIE,
                visitor_id,
                max_age=VISITOR_COOKIE_MAX_AGE,
                httponly=True,
                secure=secure,
                samesite="Lax",
            )

        response.set_cookie(
            VISIT_COOKIE,
            f"{visit_id}.{int(now_timestamp)}",
            max_age=VISIT_TIMEOUT_SECONDS,
            httponly=True,
            secure=secure,
            samesite="Lax",
        )

        return response

    def _should_track(self, request, response):

        if request.method != "GET":
            return False

        if not 200 <= response.status_code < 300:
            return False

        if not response.get("Content-Type", "").startswith("text/html"):
            return False

        if not should_track_path(request.path_info):
            return False

        if request.COOKIES.get(IGNORE_COOKIE):
            return False

        if is_bot(request) or is_prefetch(request):
            return False

        return True

    def _seen_before(self, visitor_id, user):

        if PageView.objects.filter(visitor_id=visitor_id).exists():
            return True

        return user is not None and PageView.objects.filter(user=user).exists()
