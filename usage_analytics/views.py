from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from travel.models import UserProfile

from .models import UsageEvent
from .permissions import VIEWER_GROUP_NAME, can_view_analytics


User = get_user_model()

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

    context = {
        "target_user": target_user,
        "display_name": display_name,
        "days": days,
        "excluded_ids": sorted(excluded_ids),
        "summary": summary,
        "apps": get_app_statistics(events),
    }

    return render(
        request,
        "usage_analytics/user_detail.html",
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
