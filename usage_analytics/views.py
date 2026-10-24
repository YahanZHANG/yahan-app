import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from news.models import Article
from travel.models import UserProfile

from . import stats
from .catalog import app_info
from .behavior import build_behavior
from .insights import build_insights
from .middleware import IGNORE_COOKIE, visitor_of
from .models import (
    AnalyticsExclusion,
    PageView,
    PublicNewsArticleClick,
    UserNewsArticleClick,
)
from .permissions import VIEWER_GROUP_NAME, can_view_analytics


User = get_user_model()
logger = logging.getLogger(__name__)


# =========================================================
# Helpers
# =========================================================

def require_viewer(request):

    if not can_view_analytics(request.user):
        raise PermissionDenied


def get_profiles_by_user_id(user_ids):
    """表示名取得時の重複クエリを避ける。"""

    return {
        profile.user_id: profile
        for profile in UserProfile.objects.filter(user_id__in=user_ids)
    }


def display_names(user_ids):

    user_ids = {user_id for user_id in user_ids if user_id}
    profiles = get_profiles_by_user_id(user_ids)
    usernames = dict(User.objects.filter(pk__in=user_ids).values_list("pk", "username"))

    return {
        user_id: (
            profiles[user_id].display_name if user_id in profiles else usernames.get(user_id, "")
        )
        for user_id in user_ids
    }


def visitor_label(visitor_id):

    return f"匿名 #{str(visitor_id)[:4]}"


def scope_from_request(request):

    app = request.GET.get("app", "")

    # 存在しないアプリ名は無視 (自由入力を集計クエリに流さない)
    if app and not PageView.objects.filter(app_key=app).exists():
        app = ""

    return stats.Scope(days=stats.parse_period(request.GET.get("days")), app=app)


def app_choices():

    keys = PageView.objects.values_list("app_key", flat=True).distinct()

    return sorted(
        (app_info(key) for key in keys),
        key=lambda app: (app["color"] or 99, app["name"]),
    )


# =========================================================
# Dashboard
# =========================================================

@login_required
def dashboard(request):
    """全アプリのアクセス解析。"""

    require_viewer(request)

    scope = scope_from_request(request)
    current = scope.current()

    data = stats.build_dashboard(scope)
    pages = stats.top_pages(current)
    clicks = stats.top_news_clicks(scope) if scope.app in ("", "news") else []
    users = stats.signed_in_users(current)

    names = display_names(
        [visit["user_id"] for visit in data["recent_visits"]]
        + [row["user_id"] for row in users]
    )

    for visit in data["recent_visits"]:
        visit["person"] = names.get(visit["user_id"]) or visitor_label(visit["visitor_id"])

    for row in users:
        row["display_name"] = names.get(row["user_id"]) or row["user__username"]

    context = {
        "scope": scope,
        "period_choices": stats.PERIOD_CHOICES,
        "apps_available": app_choices(),
        "selected_app": app_info(scope.app) if scope.app else None,
        "data": data,
        "insights": build_insights(scope, data, pages, clicks),
        "pages": pages,
        "clicks": clicks,
        "users": users,
        "behavior": build_behavior(scope),
        "charts": {
            "visitors": data["visitors_chart"],
            "page_views": data["page_views_chart"],
            "sources": data["sources_chart"],
            "traffic": stats.traffic_chart(scope),
            "last_day": stats.last_day_chart(scope),
        },
        **live_context(request),
    }

    return render(request, "usage_analytics/dashboard.html", context)


# =========================================================
# Live status (いま見ている人)
# =========================================================

def live_context(request):

    live = stats.live_status(stats.Scope(days=1))
    names = display_names(live["user_ids"])

    live["users"] = [
        {"id": user_id, "name": names.get(user_id) or "?"}
        for user_id in sorted(live["user_ids"], key=lambda user_id: names.get(user_id, ""))
    ]

    return {
        "live": live,
        "is_ignored_browser": bool(request.COOKIES.get(IGNORE_COOKIE)),
    }


@login_required
@never_cache
def live_status(request):
    """解析ページの「いまの状況」を30秒ごとに入れ替える用 (HTMLの一部を返す)。"""

    require_viewer(request)

    return render(request, "usage_analytics/_live.html", live_context(request))


# =========================================================
# Person detail
# =========================================================

def render_person(request, views, title, subtitle, linked_users=None, visitors=None):

    summary = stats.person_summary(views)

    if not summary["page_views"]:
        raise Http404

    return render(
        request,
        "usage_analytics/person.html",
        {
            "title": title,
            "subtitle": subtitle,
            "summary": summary,
            "timeline": stats.person_timeline(views),
            "strip": stats.activity_strip(views),
            "linked_users": linked_users or [],
            "visitors": visitors or [],
        },
    )


@login_required
def visitor_detail(request, visitor_id):
    """1つのブラウザ (訪問者) の足あと。"""

    require_viewer(request)

    scope = stats.Scope(days=stats.DEFAULT_PERIOD)
    views = scope.base().filter(visitor_id=visitor_id)

    user_ids = set(views.exclude(user=None).values_list("user_id", flat=True).distinct())
    names = display_names(user_ids)

    return render_person(
        request,
        views,
        title=visitor_label(visitor_id),
        subtitle="同じブラウザからの閲覧の記録",
        linked_users=[{"id": user_id, "name": names[user_id]} for user_id in user_ids],
    )


@login_required
def user_detail(request, user_id):
    """ログインユーザーの足あと (どのブラウザからでも)。"""

    require_viewer(request)

    target_user = get_object_or_404(User, pk=user_id)

    scope = stats.Scope(days=stats.DEFAULT_PERIOD)
    if target_user.pk in scope.excluded_user_ids:
        raise Http404

    views = scope.base().filter(user=target_user)

    return render_person(
        request,
        views,
        title=display_names([target_user.pk]).get(target_user.pk) or target_user.username,
        subtitle=f"ログインユーザー ({target_user.username}) の閲覧の記録",
    )


# =========================================================
# Settings
# =========================================================

@login_required
@require_http_methods(["GET", "POST"])
def settings_view(request):
    """集計から外すアカウントと、このブラウザを集計しない設定。"""

    require_viewer(request)

    if request.method == "POST":

        if not request.user.is_superuser:
            raise PermissionDenied

        raw_ids = request.POST.getlist("exclude_users")

        if any(not (raw.isascii() and raw.isdecimal() and len(raw) <= 20) for raw in raw_ids):
            return HttpResponseBadRequest("Invalid user ID.")

        selected = set(User.objects.filter(pk__in={int(raw) for raw in raw_ids}).values_list("pk", flat=True))

        AnalyticsExclusion.objects.exclude(user_id__in=selected).delete()
        for user_id in selected:
            AnalyticsExclusion.objects.get_or_create(user_id=user_id)

        messages.success(request, "集計から外すアカウントを更新しました。")
        return redirect("usage_analytics:settings")

    excluded = set(AnalyticsExclusion.objects.values_list("user_id", flat=True))
    accounts = list(User.objects.filter(is_active=True).order_by("username"))
    names = display_names([account.pk for account in accounts])

    return render(
        request,
        "usage_analytics/settings.html",
        {
            "accounts": [
                {
                    "id": account.pk,
                    "username": account.username,
                    "display_name": names.get(account.pk) or account.username,
                    "is_excluded": account.pk in excluded,
                }
                for account in accounts
            ],
            "is_ignored_browser": bool(request.COOKIES.get(IGNORE_COOKIE)),
        },
    )


@login_required
@require_POST
def toggle_ignore_browser(request):
    """このブラウザの閲覧を記録しない / また記録する。"""

    require_viewer(request)

    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("usage_analytics:settings")

    response = redirect(next_url)

    if request.POST.get("ignore") == "1":
        response.set_cookie(
            IGNORE_COOKIE,
            "1",
            max_age=60 * 60 * 24 * 365 * 5,
            httponly=True,
            samesite="Lax",
        )
        messages.success(request, "このブラウザの閲覧は、これから記録しません。")
    else:
        response.delete_cookie(IGNORE_COOKIE)
        messages.success(request, "このブラウザの閲覧を、また記録します。")

    return response


# =========================================================
# Access control
# =========================================================

@login_required
@require_http_methods(["GET", "POST"])
def access_control(request):
    """解析ページの閲覧権限設定。Superuserのみ。"""

    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        raw_ids = request.POST.getlist("viewer_ids")

        if any(
            not (
                raw_id.isascii()
                and raw_id.isdecimal()
                and len(raw_id) <= 20
            )
            for raw_id in raw_ids
        ):
            return HttpResponseBadRequest("Invalid user ID.")

        selected_ids = {int(raw_id) for raw_id in raw_ids}

        selected_users = User.objects.filter(
            pk__in=selected_ids,
            is_active=True,
            is_superuser=False,
        )

        if selected_users.count() != len(selected_ids):
            return HttpResponseBadRequest("Invalid user selection.")

        group, _ = Group.objects.get_or_create(
            name=VIEWER_GROUP_NAME
        )
        group.user_set.set(selected_users)

        messages.success(request, "閲覧権限を更新しました。")
        return redirect("usage_analytics:access_control")

    group = Group.objects.filter(
        name=VIEWER_GROUP_NAME
    ).first()

    viewer_ids = set()
    if group:
        viewer_ids = set(
            group.user_set.values_list("pk", flat=True)
        )

    users = list(
        User.objects.filter(
            is_active=True,
            is_superuser=False,
        ).order_by("username")
    )
    names = display_names([user.pk for user in users])

    accounts = [
        {
            "id": user.pk,
            "username": user.username,
            "display_name": names.get(user.pk) or user.username,
            "is_viewer": user.pk in viewer_ids,
        }
        for user in users
    ]

    return render(
        request,
        "usage_analytics/access_control.html",
        {"accounts": accounts},
    )


# =========================================================
# Public News article click
# =========================================================

def public_news_article_click(
    request,
    article_id,
):
    """
    Swiss Newsの記事クリックを記録して、
    元記事へリダイレクトする。

    匿名ユーザー：
        PublicNewsArticleClick

    ログインユーザー：
        UserNewsArticleClick
    """

    article = get_object_or_404(
        Article.objects.select_related(
            "source"
        ),
        pk=article_id,
    )

    destination_url = article.source_url

    article_title = (
        article.title_ja
        or article.title_original
    )

    source_name = article.source.name

    try:

        if request.user.is_authenticated:

            UserNewsArticleClick.objects.create(
                user=request.user,
                article_id=article.pk,
                article_title=article_title,
                source_name=source_name,
                destination_url=destination_url,
            )

        else:

            visitor_id, visit_id = visitor_of(request)

            origin_path = request.GET.get(
                "origin",
                "",
            ).split("?", 1)[0]

            if not origin_path.startswith("/news"):
                origin_path = ""

            if visitor_id:

                PublicNewsArticleClick.objects.create(
                    visitor_id=visitor_id,
                    visit_id=visit_id,
                    article_id=article.pk,
                    article_title=article_title,
                    source_name=source_name,
                    destination_url=destination_url,
                    origin_path=origin_path[:500],
                )

    except DatabaseError:

        logger.exception(
            "Failed to save news article click."
        )

    return redirect(
        destination_url
    )


# =========================================================
# Old URLs
# =========================================================

@login_required
def legacy_redirect(request, **kwargs):
    """前の解析ページのURL (ブックマーク用) を新しいページへ。"""

    require_viewer(request)

    if "visitor_id" in kwargs:
        return redirect("usage_analytics:visitor_detail", visitor_id=kwargs["visitor_id"])

    if "user_id" in kwargs:
        return redirect("usage_analytics:user_detail", user_id=kwargs["user_id"])

    return redirect(reverse("usage_analytics:dashboard") + "?app=news")
