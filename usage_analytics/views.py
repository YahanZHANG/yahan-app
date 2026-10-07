import logging

from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.models import (
    Count,
    Max,
    Min,
    Q,
)
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from news.models import Article
from travel.models import UserProfile

from .models import (
    PublicNewsArticleClick,
    PublicNewsEvent,
    UsageEvent,
    UserNewsArticleClick,
    UserNewsEvent,
)

from .permissions import VIEWER_GROUP_NAME, can_view_analytics


User = get_user_model()
logger = logging.getLogger(__name__)

# URLに除外設定がない場合だけ、デフォルトで除外するアカウント。
DEFAULT_EXCLUDED_USERNAMES = (
    "admin",
    "yahan",
    "fumimasakubo",
)


# =========================================================
# Helpers
# =========================================================

def get_excluded_user_ids(request):
    """URLの明示的な指定を優先し、未指定なら3アカウントを除外。"""

    # filter_applied=1 があれば、exclude_users が0件でも
    # 「全員を集計に含める」というユーザーの選択として扱う。
    filter_is_explicit = (
        "filter_applied" in request.GET
        or "exclude_users" in request.GET
    )

    if not filter_is_explicit:
        return set(
            User.objects.filter(
                username__in=DEFAULT_EXCLUDED_USERNAMES
            ).values_list("pk", flat=True)
        )

    requested_ids = set()

    for value in request.GET.getlist("exclude_users"):
        if (
            value.isascii()
            and value.isdecimal()
            and len(value) <= 20
        ):
            requested_ids.add(int(value))

    return set(
        User.objects.filter(
            pk__in=requested_ids
        ).values_list("pk", flat=True)
    )


def get_period_events(request):
    """集計期間・除外対象・フィルタ済みUsageEventを返す。"""

    days = request.GET.get("days", "7")
    if days not in {"7", "30", "all"}:
        days = "7"

    excluded_ids = get_excluded_user_ids(request)
    events = UsageEvent.objects.all()

    if days != "all":
        start = timezone.now() - timedelta(days=int(days))
        events = events.filter(accessed_at__gte=start)

    if excluded_ids:
        events = events.exclude(user_id__in=excluded_ids)

    return days, excluded_ids, events


def get_profiles_by_user_id(users):
    """表示名取得時の重複クエリを避ける。"""
    return {
        profile.user_id: profile
        for profile in UserProfile.objects.filter(
            user_id__in=[user.pk for user in users]
        )
    }


# =========================================================
# App statistics
# =========================================================

def get_app_statistics(events):
    """アプリごとの利用状況を集計する。"""

    local_date = TruncDate(
        "accessed_at",
        tzinfo=timezone.get_current_timezone(),
    )

    statistics = (
        events.values("app_key")
        .annotate(
            users=Count("user_id", distinct=True),
            page_views=Count("id"),
            visits=Count("id", filter=Q(is_visit_start=True)),
            active_days=Count(local_date, distinct=True),
        )
    )

    statistics_map = {
        item["app_key"]: item for item in statistics
    }

    apps = []
    for app_key, name in UsageEvent.AppKey.choices:
        item = statistics_map.get(app_key, {})
        apps.append({
            "key": app_key,
            "name": name,
            "users": item.get("users", 0),
            "page_views": item.get("page_views", 0),
            "visits": item.get("visits", 0),
            "active_days": item.get("active_days", 0),
        })

    return apps


# =========================================================
# Public News statistics
# =========================================================

def get_public_news_statistics(days):
    """
    ログインしていない公開Yahan News閲覧者の
    匿名アクセスを集計する。
    """

    events = PublicNewsEvent.objects.all()

    if days != "all":

        start = (
            timezone.now()
            - timedelta(days=int(days))
        )

        events = events.filter(
            accessed_at__gte=start
        )

    visitors = (
        events
        .values("visitor_id")
        .distinct()
        .count()
    )

    visits = (
        events
        .filter(
            is_visit_start=True
        )
        .count()
    )

    page_views = events.count()

    return {
        "visitors": visitors,
        "visits": visits,
        "page_views": page_views,
    }


# =========================================================
# Public News detail
# =========================================================

@login_required
def public_news_detail(request):
    """
    公開Swiss Newsの利用状況を詳しく表示する。

    匿名Visitorについて、
    訪問者数・訪問回数・ページ閲覧数・
    ページ別利用状況・Visitor別利用状況を集計する。

    記事クリックについては、
    匿名ユーザーとログインユーザーの両方を集計する。
    """

    # =====================================================
    # Permission
    # =====================================================

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied

    # =====================================================
    # Period
    # =====================================================

    days = request.GET.get(
        "days",
        "7",
    )

    if days not in {
        "7",
        "30",
        "all",
    }:
        days = "7"

    # =====================================================
    # Public News events
    # =====================================================

    events = (
        PublicNewsEvent.objects.all()
    )

    if days != "all":

        start = (
            timezone.now()
            - timedelta(
                days=int(days)
            )
        )

        events = events.filter(
            accessed_at__gte=start
        )

    # =====================================================
    # Summary
    # =====================================================

    summary = events.aggregate(

        visitors=Count(
            "visitor_id",
            distinct=True,
        ),

        page_views=Count(
            "id"
        ),

        first_seen=Min(
            "accessed_at"
        ),

        last_seen=Max(
            "accessed_at"
        ),

    )

    summary["visits"] = (
        events
        .filter(
            is_visit_start=True
        )
        .count()
    )

    # =====================================================
    # Page statistics
    # =====================================================

    pages = list(

        events
        .values(
            "path"
        )
        .annotate(

            page_views=Count(
                "id"
            ),

            visitors=Count(
                "visitor_id",
                distinct=True,
            ),

            last_seen=Max(
                "accessed_at"
            ),

        )
        .order_by(
            "-page_views",
            "-last_seen",
        )

    )

    # =====================================================
    # Visitor statistics
    # =====================================================

    visitors = list(

        events
        .values(
            "visitor_id"
        )
        .annotate(

            page_views=Count(
                "id"
            ),

            visits=Count(
                "id",
                filter=Q(
                    is_visit_start=True
                ),
            ),

            first_seen=Min(
                "accessed_at"
            ),

            last_seen=Max(
                "accessed_at"
            ),

        )
        .order_by(
            "-last_seen"
        )

    )

    # Short anonymous ID for display

    for visitor in visitors:

        visitor["short_id"] = (
            str(
                visitor["visitor_id"]
            )[:8]
        )

    # =====================================================
    # Recent events
    # =====================================================

    recent_events = list(

        events
        .order_by(
            "-accessed_at"
        )[:100]

    )

    for event in recent_events:

        event.short_id = (
            str(
                event.visitor_id
            )[:8]
        )

    # =====================================================
    # Article clicks
    # =====================================================

    public_clicks = (
        PublicNewsArticleClick.objects.all()
    )

    user_clicks = (
        UserNewsArticleClick.objects.all()
    )

    if days != "all":

        public_clicks = (
            public_clicks.filter(
                clicked_at__gte=start
            )
        )

        user_clicks = (
            user_clicks.filter(
                clicked_at__gte=start
            )
        )

    # =====================================================
    # Click summary
    # =====================================================

    anonymous_click_count = (
        public_clicks.count()
    )

    authenticated_click_count = (
        user_clicks.count()
    )

    click_summary = {

        "anonymous": (
            anonymous_click_count
        ),

        "authenticated": (
            authenticated_click_count
        ),

        "total": (
            anonymous_click_count
            + authenticated_click_count
        ),

    }

    # =====================================================
    # Context
    # =====================================================

    context = {

        "days": days,

        "summary": summary,

        "pages": pages,

        "visitors": visitors,

        "recent_events": recent_events,

        "click_summary": click_summary,

    }

    return render(
        request,
        "usage_analytics/public_news_detail.html",
        context,
    )

# =========================================================
# Public News visitor detail
# =========================================================

@login_required
def public_news_visitor_detail(
    request,
    visitor_id,
):
    """
    公開Swiss Newsの匿名訪問者ごとの
    アクセス経路を表示する。
    """

    if not can_view_analytics(request.user):
        raise PermissionDenied

    days = request.GET.get(
        "days",
        "7",
    )

    if days not in {
        "7",
        "30",
        "all",
    }:
        days = "7"

    events = PublicNewsEvent.objects.filter(
        visitor_id=visitor_id
    )

    if days != "all":

        start = (
            timezone.now()
            - timedelta(
                days=int(days)
            )
        )

        events = events.filter(
            accessed_at__gte=start
        )

    if not events.exists():
        raise Http404

    # =====================================================
    # Summary
    # =====================================================

    summary = events.aggregate(
        page_views=Count("id"),
        first_seen=Min("accessed_at"),
        last_seen=Max("accessed_at"),
    )

    summary["visits"] = (
        events
        .filter(
            is_visit_start=True
        )
        .count()
    )

    # =====================================================
    # Access history
    # =====================================================

    page_events = list(
        events.order_by(
            "accessed_at"
        )
    )

    click_events = (
        PublicNewsArticleClick.objects
        .filter(
            visitor_id=visitor_id
        )
    )

    if days != "all":

        click_events = click_events.filter(
            clicked_at__gte=start
        )

    click_events = list(
        click_events.order_by(
            "clicked_at"
        )
    )


    # =====================================================
    # Merge page views and article clicks
    # =====================================================

    access_history = []

    for event in page_events:

        access_history.append({
            "type": "page",
            "timestamp": event.accessed_at,
            "path": event.path,
            "visit_id": event.visit_id,
            "is_visit_start": event.is_visit_start,
        })


    for click in click_events:

        access_history.append({
            "type": "click",
            "timestamp": click.clicked_at,
            "article_title": click.article_title,
            "source_name": click.source_name,
            "destination_url": click.destination_url,
            "origin_path": click.origin_path,
            "visit_id": click.visit_id,
            "is_visit_start": False,
        })


    access_history.sort(
        key=lambda item: item["timestamp"]
    )


    # =====================================================
    # Visit number
    # =====================================================

    visit_number = 0

    for event in access_history:

        if event["is_visit_start"]:
            visit_number += 1

        if visit_number == 0:
            visit_number = 1

        event["visit_number"] = visit_number

    # =====================================================
    # Context
    # =====================================================

    context = {
        "days": days,
        "visitor_id": visitor_id,
        "short_id": str(visitor_id)[:8],
        "summary": summary,
        "access_history": access_history,
    }

    return render(
        request,
        "usage_analytics/public_news_visitor_detail.html",
        context,
    )
    
# =========================================================
# Public News article click
# =========================================================

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

        # ---------------------------------------------
        # Authenticated user
        # ---------------------------------------------

        if request.user.is_authenticated:

            UserNewsArticleClick.objects.create(
                user=request.user,
                article_id=article.pk,
                article_title=article_title,
                source_name=source_name,
                destination_url=destination_url,
            )

        # ---------------------------------------------
        # Anonymous visitor
        # ---------------------------------------------

        else:

            visitor_id = request.session.get(
                "public_news_visitor_id"
            )

            visit_id = request.session.get(
                "public_news_visit_id"
            )

            origin_path = request.GET.get(
                "origin",
                "",
            )

            origin_path = (
                origin_path
                .split(
                    "?",
                    1,
                )[0]
            )

            if not origin_path.startswith(
                "/news"
            ):
                origin_path = ""

            origin_path = origin_path[:500]

            if visitor_id:

                PublicNewsArticleClick.objects.create(
                    visitor_id=visitor_id,
                    visit_id=visit_id,
                    article_id=article.pk,
                    article_title=article_title,
                    source_name=source_name,
                    destination_url=destination_url,
                    origin_path=origin_path,
                )

    except DatabaseError:

        logger.exception(
            "Failed to save news article click."
        )

    return redirect(
        destination_url
    )

# =========================================================
# Dashboard
# =========================================================

@login_required
def dashboard(request):
    """全体・アプリ別・ユーザー別の利用状況を表示する。"""

    if not can_view_analytics(request.user):
        raise PermissionDenied

    days, excluded_ids, events = get_period_events(request)

    target_users = User.objects.all()
    if excluded_ids:
        target_users = target_users.exclude(pk__in=excluded_ids)

    registered_users = target_users.count()
    active_users = events.values("user_id").distinct().count()
    total_page_views = events.count()
    total_visits = events.filter(is_visit_start=True).count()

    apps = get_app_statistics(events)

    public_news = (
        get_public_news_statistics(
            days
        )
    )

    local_date = TruncDate(
        "accessed_at",
        tzinfo=timezone.get_current_timezone(),
    )

    user_statistics = (
        events.values("user_id")
        .annotate(
            page_views=Count("id"),
            visits=Count("id", filter=Q(is_visit_start=True)),
            active_days=Count(local_date, distinct=True),
            last_seen=Max("accessed_at"),
        )
    )

    statistics_map = {
        item["user_id"]: item for item in user_statistics
    }

    all_users = list(target_users.order_by("username"))
    profiles = get_profiles_by_user_id(all_users)

    users = []
    for user in all_users:
        statistics = statistics_map.get(user.pk, {})
        profile = profiles.get(user.pk)

        users.append({
            "id": user.pk,
            "username": user.username,
            "display_name": (
                profile.display_name if profile else user.username
            ),
            "page_views": statistics.get("page_views", 0),
            "visits": statistics.get("visits", 0),
            "active_days": statistics.get("active_days", 0),
            "last_seen": statistics.get("last_seen"),
        })

    users.sort(
        key=lambda item: (
            item["page_views"], item["active_days"]
        ),
        reverse=True,
    )

    context = {
        "days": days,
        "excluded_ids": sorted(excluded_ids),
        "registered_users": registered_users,
        "active_users": active_users,
        "total_page_views": total_page_views,
        "total_visits": total_visits,
        "apps": apps,
        "users": users,
        "public_news": public_news,
    }

    return render(
        request,
        "usage_analytics/dashboard.html",
        context,
    )


# =========================================================
# Analytics filters
# =========================================================

@login_required
def filters(request):
    """集計から除外するユーザーを選ぶ画面。"""

    if not can_view_analytics(request.user):
        raise PermissionDenied

    days, excluded_ids, _ = get_period_events(request)

    selectable_users = list(
        User.objects.all().order_by("username")
    )
    profiles = get_profiles_by_user_id(selectable_users)

    exclusion_accounts = []
    for account in selectable_users:
        profile = profiles.get(account.pk)
        exclusion_accounts.append({
            "id": account.pk,
            "username": account.username,
            "display_name": (
                profile.display_name if profile else account.username
            ),
            "is_excluded": account.pk in excluded_ids,
        })

    context = {
        "days": days,
        "excluded_ids": sorted(excluded_ids),
        "exclusion_accounts": exclusion_accounts,
    }

    return render(
        request,
        "usage_analytics/filters.html",
        context,
    )


# =========================================================
# User detail
# =========================================================

@login_required
def user_detail(request, user_id):
    """ユーザー別の利用状況を表示する。"""

    if not can_view_analytics(request.user):
        raise PermissionDenied

    target_user = get_object_or_404(User, pk=user_id)
    days, excluded_ids, events = get_period_events(request)

    # 除外中のユーザーは、その条件のままでは詳細表示しない。
    if target_user.pk in excluded_ids:
        raise Http404

    profile = UserProfile.objects.filter(user=target_user).first()
    display_name = (
        profile.display_name if profile else target_user.username
    )
    events = events.filter(user=target_user)

    local_date = TruncDate(
        "accessed_at",
        tzinfo=timezone.get_current_timezone(),
    )

    summary = events.aggregate(
        page_views=Count("id"),
        visits=Count("id", filter=Q(is_visit_start=True)),
        active_days=Count(local_date, distinct=True),
        last_seen=Max("accessed_at"),
    )

    # =====================================================
    # Swiss News detailed statistics
    # =====================================================

    news_events = UserNewsEvent.objects.filter(
        user=target_user
    )

    news_clicks = UserNewsArticleClick.objects.filter(
        user=target_user
    )

    if days != "all":

        start = (
            timezone.now()
            - timedelta(
                days=int(days)
            )
        )

        news_events = news_events.filter(
            accessed_at__gte=start
        )

        news_clicks = news_clicks.filter(
            clicked_at__gte=start
        )

    news_summary = {
        "visits": (
            news_events
            .filter(
                is_visit_start=True
            )
            .count()
        ),
        "page_views": (
            news_events.count()
        ),
        "article_clicks": (
            news_clicks.count()
        ),
    }

    context = {
        "target_user": target_user,
        "display_name": display_name,
        "days": days,
        "excluded_ids": sorted(excluded_ids),
        "summary": summary,
        "news_summary": news_summary,
        "apps": get_app_statistics(events),
    }

    return render(
        request,
        "usage_analytics/user_detail.html",
        context,
    )

@login_required
def user_news_detail(
    request,
    user_id,
):
    """
    ログインユーザーのSwiss News内での
    ページ閲覧と記事クリックを時系列で表示する。
    """

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied

    # =====================================================
    # Target user
    # =====================================================

    User = get_user_model()

    target_user = get_object_or_404(
        User,
        pk=user_id,
    )

    display_name = (
        target_user.get_full_name()
        or target_user.username
    )

    # =====================================================
    # Period
    # =====================================================

    days = request.GET.get(
        "days",
        "7",
    )

    if days not in {
        "7",
        "30",
        "all",
    }:
        days = "7"

    # =====================================================
    # Page events
    # =====================================================

    events = UserNewsEvent.objects.filter(
        user=target_user
    )

    clicks = UserNewsArticleClick.objects.filter(
        user=target_user
    )

    if days != "all":

        start = (
            timezone.now()
            - timedelta(
                days=int(days)
            )
        )

        events = events.filter(
            accessed_at__gte=start
        )

        clicks = clicks.filter(
            clicked_at__gte=start
        )

    # =====================================================
    # Summary
    # =====================================================

    summary = events.aggregate(
        page_views=Count("id"),
        first_seen=Min("accessed_at"),
        last_seen=Max("accessed_at"),
    )

    summary["visits"] = (
        events
        .filter(
            is_visit_start=True
        )
        .count()
    )

    summary["article_clicks"] = (
        clicks.count()
    )

    # =====================================================
    # Merge page views and article clicks
    # =====================================================

    access_history = []

    for event in events:

        access_history.append({
            "type": "page",
            "timestamp": event.accessed_at,
            "path": event.path,
            "is_visit_start": event.is_visit_start,
        })

    for click in clicks:

        access_history.append({
            "type": "click",
            "timestamp": click.clicked_at,
            "article_title": click.article_title,
            "source_name": click.source_name,
            "destination_url": click.destination_url,
            "is_visit_start": False,
        })

    access_history.sort(
        key=lambda item: item["timestamp"]
    )

    # =====================================================
    # Visit number
    # =====================================================

    visit_number = 0

    for event in access_history:

        if event["is_visit_start"]:
            visit_number += 1

        if visit_number == 0:
            visit_number = 1

        event["visit_number"] = (
            visit_number
        )

    # =====================================================
    # Context
    # =====================================================

    context = {
        "target_user": target_user,
        "display_name": display_name,
        "days": days,
        "summary": summary,
        "access_history": access_history,
    }

    return render(
        request,
        "usage_analytics/user_news_detail.html",
        context,
    )

# =========================================================
# Viewer access settings
# =========================================================

@login_required
@require_http_methods(["GET", "POST"])
def access_control(request):
    """管理ダッシュボードの閲覧権限設定。Superuserのみ。"""

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
    profiles = get_profiles_by_user_id(users)

    accounts = []
    for user in users:
        profile = profiles.get(user.pk)
        accounts.append({
            "id": user.pk,
            "username": user.username,
            "display_name": (
                profile.display_name if profile else user.username
            ),
            "is_viewer": user.pk in viewer_ids,
        })

    return render(
        request,
        "usage_analytics/access_control.html",
        {"accounts": accounts},
    )

# =========================================================
# Swiss News analytics helpers
# =========================================================


def percentage(
    numerator,
    denominator,
):
    if not denominator:
        return 0

    return round(
        numerator
        / denominator
        * 100,
        1,
    )


def get_news_period_start(days):
    """
    7日・30日の集計開始日時を
    ローカル時間の0:00で返す。
    """

    if days == "all":
        return None

    now_local = timezone.localtime(
        timezone.now()
    )

    today_start = now_local.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return (
        today_start
        - timedelta(
            days=int(days) - 1
        )
    )


def get_news_retention(
    events,
    retention_days,
):
    """
    初回訪問から指定日数以上経過したVisitorのうち、
    指定日数後にも再訪しているVisitorの割合。

    例：
    7日Retention
        初回訪問から7日以上経過したVisitorが母数。
        初回訪問から7日後以降にもアクセスがあればReturned。
    """

    now = timezone.now()

    eligible_before = (
        now
        - timedelta(
            days=retention_days
        )
    )

    cohorts = (
        events
        .values(
            "visitor_id"
        )
        .annotate(
            first_seen=Min(
                "accessed_at"
            ),
            last_seen=Max(
                "accessed_at"
            ),
        )
    )

    eligible = 0
    returned = 0

    for cohort in cohorts.iterator():

        first_seen = cohort[
            "first_seen"
        ]

        last_seen = cohort[
            "last_seen"
        ]

        if first_seen is None:
            continue

        if first_seen > eligible_before:
            continue

        eligible += 1

        retention_threshold = (
            first_seen
            + timedelta(
                days=retention_days
            )
        )

        if (
            last_seen
            and last_seen
            >= retention_threshold
        ):
            returned += 1

    if eligible == 0:

        rate = None

    else:

        rate = percentage(
            returned,
            eligible,
        )

    return {
        "rate": rate,
        "returned": returned,
        "eligible": eligible,
    }


# =========================================================
# Swiss News Analytics
# =========================================================


@login_required
def news_app_detail(request):
    """
    公開Swiss NewsのAnalytics。

    メイン指標は匿名Visitorを対象とする。

    ログインユーザーについては
    ページ下部に補助情報として別表示する。
    """

    # =====================================================
    # Permission
    # =====================================================

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied


    # =====================================================
    # Period
    # =====================================================

    days = request.GET.get(
        "days",
        "7",
    )

    if days not in {
        "7",
        "30",
        "all",
    }:
        days = "7"


    period_start = (
        get_news_period_start(
            days
        )
    )


    # =====================================================
    # Base querysets
    # =====================================================

    all_anonymous_events = (
        PublicNewsEvent.objects.all()
    )

    all_anonymous_clicks = (
        PublicNewsArticleClick.objects.all()
    )

    all_authenticated_events = (
        UserNewsEvent.objects.all()
    )

    all_authenticated_clicks = (
        UserNewsArticleClick.objects.all()
    )


    # =====================================================
    # Selected-period querysets
    # =====================================================

    anonymous_events = (
        all_anonymous_events
    )

    anonymous_clicks = (
        all_anonymous_clicks
    )

    authenticated_events = (
        all_authenticated_events
    )

    authenticated_clicks = (
        all_authenticated_clicks
    )


    if period_start is not None:

        anonymous_events = (
            anonymous_events.filter(
                accessed_at__gte=(
                    period_start
                )
            )
        )

        anonymous_clicks = (
            anonymous_clicks.filter(
                clicked_at__gte=(
                    period_start
                )
            )
        )

        authenticated_events = (
            authenticated_events.filter(
                accessed_at__gte=(
                    period_start
                )
            )
        )

        authenticated_clicks = (
            authenticated_clicks.filter(
                clicked_at__gte=(
                    period_start
                )
            )
        )


    # =====================================================
    # Anonymous summary
    # =====================================================

    anonymous_users = (
        anonymous_events
        .values(
            "visitor_id"
        )
        .distinct()
        .count()
    )

    anonymous_visits = (
        anonymous_events
        .filter(
            is_visit_start=True
        )
        .count()
    )

    anonymous_page_views = (
        anonymous_events.count()
    )

    anonymous_article_clicks = (
        anonymous_clicks.count()
    )


    anonymous_summary = {

        "users": (
            anonymous_users
        ),

        "visits": (
            anonymous_visits
        ),

        "page_views": (
            anonymous_page_views
        ),

        "article_clicks": (
            anonymous_article_clicks
        ),

    }


    # =====================================================
    # Growth
    # =====================================================

    now_local = timezone.localtime(
        timezone.now()
    )

    today_start = now_local.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


    wau_start = (
        today_start
        - timedelta(
            days=6
        )
    )


    mau_start = (
        today_start
        - timedelta(
            days=29
        )
    )


    dau = (
        all_anonymous_events
        .filter(
            accessed_at__gte=(
                today_start
            )
        )
        .values(
            "visitor_id"
        )
        .distinct()
        .count()
    )


    wau = (
        all_anonymous_events
        .filter(
            accessed_at__gte=(
                wau_start
            )
        )
        .values(
            "visitor_id"
        )
        .distinct()
        .count()
    )


    mau = (
        all_anonymous_events
        .filter(
            accessed_at__gte=(
                mau_start
            )
        )
        .values(
            "visitor_id"
        )
        .distinct()
        .count()
    )


    new_visitors = (
        anonymous_events
        .filter(
            is_new_visitor=True
        )
        .values(
            "visitor_id"
        )
        .distinct()
        .count()
    )


    returning_visitors = max(
        anonymous_users
        - new_visitors,
        0,
    )


    growth = {

        "dau": dau,

        "wau": wau,

        "mau": mau,

        "dau_mau_rate": (
            percentage(
                dau,
                mau,
            )
        ),

        "new_visitors": (
            new_visitors
        ),

        "returning_visitors": (
            returning_visitors
        ),

        "returning_rate": (
            percentage(
                returning_visitors,
                anonymous_users,
            )
        ),

    }


    # =====================================================
    # Retention
    # =====================================================

    retention_7 = (
        get_news_retention(
            all_anonymous_events,
            7,
        )
    )


    retention_30 = (
        get_news_retention(
            all_anonymous_events,
            30,
        )
    )


    retention = {

        "day7_rate": (
            retention_7["rate"]
        ),

        "day7_returned": (
            retention_7["returned"]
        ),

        "day7_eligible": (
            retention_7["eligible"]
        ),

        "day30_rate": (
            retention_30["rate"]
        ),

        "day30_returned": (
            retention_30[
                "returned"
            ]
        ),

        "day30_eligible": (
            retention_30[
                "eligible"
            ]
        ),

    }


    # =====================================================
    # Engagement
    # =====================================================

    article_clickers = (
        anonymous_clicks
        .values(
            "visitor_id"
        )
        .distinct()
        .count()
    )


    if anonymous_visits:

        pages_per_visit = round(
            anonymous_page_views
            / anonymous_visits,
            1,
        )

    else:

        pages_per_visit = 0.0


    engagement = {

        "visits": (
            anonymous_visits
        ),

        "page_views": (
            anonymous_page_views
        ),

        "pages_per_visit": (
            pages_per_visit
        ),

        "article_clicks": (
            anonymous_article_clicks
        ),

        "article_clickers": (
            article_clickers
        ),

        "clicker_rate": (
            percentage(
                article_clickers,
                anonymous_users,
            )
        ),

    }


    # =====================================================
    # Daily chart date range
    # =====================================================

    local_today = timezone.localdate()


    if days != "all":

        chart_dates = [

            (
                period_start.date()
                + timedelta(
                    days=index
                )
            )

            for index in range(
                int(days)
            )

        ]

    else:

        first_event = (
            all_anonymous_events
            .order_by(
                "accessed_at"
            )
            .values_list(
                "accessed_at",
                flat=True,
            )
            .first()
        )


        if first_event:

            first_date = (
                timezone.localtime(
                    first_event
                ).date()
            )

        else:

            first_date = (
                local_today
            )


        total_days = (

            (
                local_today
                - first_date
            ).days

            + 1
        )


        chart_dates = [

            (
                first_date
                + timedelta(
                    days=index
                )
            )

            for index in range(
                total_days
            )

        ]


    # =====================================================
    # Daily chart empty buckets
    # =====================================================

    daily_map = {

        date: {

            "active_visitors": 0,

            "new_visitors": 0,

            "visits": 0,

            "article_clicks": 0,

        }

        for date in chart_dates

    }


    # =====================================================
    # Daily page activity
    # =====================================================

    daily_event_rows = (

        anonymous_events
        .annotate(
            local_date=TruncDate(
                "accessed_at",
                tzinfo=(
                    timezone
                    .get_current_timezone()
                ),
            )
        )
        .values(
            "local_date"
        )
        .annotate(

            active_visitors=Count(
                "visitor_id",
                distinct=True,
            ),

            new_visitors=Count(
                "visitor_id",
                filter=Q(
                    is_new_visitor=True
                ),
                distinct=True,
            ),

            visits=Count(
                "id",
                filter=Q(
                    is_visit_start=True
                ),
            ),

        )
    )


    for row in daily_event_rows:

        date = row[
            "local_date"
        ]

        if date not in daily_map:
            continue

        daily_map[
            date
        ][
            "active_visitors"
        ] = row[
            "active_visitors"
        ]

        daily_map[
            date
        ][
            "new_visitors"
        ] = row[
            "new_visitors"
        ]

        daily_map[
            date
        ][
            "visits"
        ] = row[
            "visits"
        ]


    # =====================================================
    # Daily article clicks
    # =====================================================

    daily_click_rows = (

        anonymous_clicks
        .annotate(
            local_date=TruncDate(
                "clicked_at",
                tzinfo=(
                    timezone
                    .get_current_timezone()
                ),
            )
        )
        .values(
            "local_date"
        )
        .annotate(
            article_clicks=Count(
                "id"
            )
        )
    )


    for row in daily_click_rows:

        date = row[
            "local_date"
        ]

        if date not in daily_map:
            continue

        daily_map[
            date
        ][
            "article_clicks"
        ] = row[
            "article_clicks"
        ]


    daily_chart_data = []


    for date in chart_dates:

        daily_chart_data.append({

            "date": (
                f"{date.month}/{date.day}"
                if days != "all"
                else (
                    f"{date.year}/"
                    f"{date.month}/"
                    f"{date.day}"
                )
            ),

            "active_visitors": (
                daily_map[
                    date
                ][
                    "active_visitors"
                ]
            ),

            "new_visitors": (
                daily_map[
                    date
                ][
                    "new_visitors"
                ]
            ),

            "visits": (
                daily_map[
                    date
                ][
                    "visits"
                ]
            ),

            "article_clicks": (
                daily_map[
                    date
                ][
                    "article_clicks"
                ]
            ),

        })


    # =====================================================
    # Acquisition
    # =====================================================

    acquisition_map = {}


    visit_starts = (

        anonymous_events
        .filter(
            is_visit_start=True
        )
        .values(
            "visitor_id",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "referrer_host",
        )
    )


    for event in visit_starts.iterator():

        source = (
            event["utm_source"]
            or event["referrer_host"]
            or "direct"
        )


        if event["utm_medium"]:

            medium = (
                event[
                    "utm_medium"
                ]
            )

        elif event["referrer_host"]:

            medium = "referral"

        else:

            medium = "direct"


        campaign = (
            event[
                "utm_campaign"
            ]
            or ""
        )


        key = (
            source,
            medium,
            campaign,
        )


        if key not in acquisition_map:

            acquisition_map[key] = {

                "source": source,

                "medium": medium,

                "campaign": campaign,

                "visitors": set(),

                "visits": 0,

            }


        acquisition_map[
            key
        ][
            "visitors"
        ].add(
            event[
                "visitor_id"
            ]
        )


        acquisition_map[
            key
        ][
            "visits"
        ] += 1


    acquisition = []


    for item in acquisition_map.values():

        acquisition.append({

            "source": (
                item["source"]
            ),

            "medium": (
                item["medium"]
            ),

            "campaign": (
                item["campaign"]
            ),

            "visitors": len(
                item["visitors"]
            ),

            "visits": (
                item["visits"]
            ),

        })


    acquisition.sort(
        key=lambda item: (
            item["visits"],
            item["visitors"],
        ),
        reverse=True,
    )


    acquisition = (
        acquisition[:20]
    )


    # =====================================================
    # Devices
    # =====================================================

    latest_device_by_visitor = {}


    device_rows = (

        anonymous_events
        .order_by(
            "accessed_at"
        )
        .values(
            "visitor_id",
            "device_type",
        )
    )


    for row in device_rows.iterator():

        latest_device_by_visitor[
            row["visitor_id"]
        ] = (
            row["device_type"]
            or "other"
        )


    device_counts = {}


    for device_type in (
        latest_device_by_visitor
        .values()
    ):

        device_counts[
            device_type
        ] = (
            device_counts.get(
                device_type,
                0,
            )
            + 1
        )


    device_labels = {

        "mobile": "Mobile",

        "desktop": "Desktop",

        "tablet": "Tablet",

        "other": "Other",

    }


    devices = []


    for (
        device_type,
        visitors_count,
    ) in device_counts.items():

        devices.append({

            "label": (
                device_labels.get(
                    device_type,
                    device_type,
                )
            ),

            "visitors": (
                visitors_count
            ),

            "percentage": (
                percentage(
                    visitors_count,
                    anonymous_users,
                )
            ),

        })


    devices.sort(
        key=lambda item: (
            item["visitors"]
        ),
        reverse=True,
    )


    # =====================================================
    # Top articles
    # =====================================================

    top_articles = list(

        anonymous_clicks
        .values(
            "article_id",
            "article_title",
            "source_name",
        )
        .annotate(

            visitors=Count(
                "visitor_id",
                distinct=True,
            ),

            clicks=Count(
                "id"
            ),

        )
        .order_by(
            "-clicks",
            "-visitors",
        )[:20]

    )


    # =====================================================
    # Top pages
    # =====================================================

    top_pages = list(

        anonymous_events
        .values(
            "path"
        )
        .annotate(

            visitors=Count(
                "visitor_id",
                distinct=True,
            ),

            page_views=Count(
                "id"
            ),

        )
        .order_by(
            "-page_views",
            "-visitors",
        )[:20]

    )


    # =====================================================
    # Authenticated summary
    # =====================================================

    authenticated_summary = {

        "users": (

            authenticated_events
            .values(
                "user_id"
            )
            .distinct()
            .count()

        ),

        "visits": (

            authenticated_events
            .filter(
                is_visit_start=True
            )
            .count()

        ),

        "page_views": (

            authenticated_events
            .count()

        ),

        "article_clicks": (

            authenticated_clicks
            .count()

        ),

    }


    # =====================================================
    # Context
    # =====================================================

    context = {

        "days": days,

        "growth": growth,

        "retention": retention,

        "engagement": engagement,

        "daily_chart_data": (
            daily_chart_data
        ),

        "acquisition": (
            acquisition
        ),

        "devices": devices,

        "top_articles": (
            top_articles
        ),

        "top_pages": (
            top_pages
        ),

        "anonymous_summary": (
            anonymous_summary
        ),

        "authenticated_summary": (
            authenticated_summary
        ),

    }


    return render(
        request,
        "usage_analytics/news_app_detail.html",
        context,
    )