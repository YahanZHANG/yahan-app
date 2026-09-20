from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate

from django.http import (
    Http404,
    HttpResponseBadRequest,
)

from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from django.utils import timezone
from django.views.decorators.http import require_http_methods

from travel.models import UserProfile

from .models import UsageEvent

from .permissions import (
    VIEWER_GROUP_NAME,
    can_view_analytics,
)


User = get_user_model()


# =========================================================
# Helpers
# =========================================================

def get_period_events(request):
    """
    集計期間と除外対象ユーザーを取得する。

    Returns:
        days
        excluded_ids
        events
    """

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
    # Selected excluded users
    # =====================================================

    raw_ids = request.GET.getlist(
        "exclude_users"
    )

    requested_ids = set()

    for value in raw_ids:

        if (
            value.isascii()
            and value.isdecimal()
            and len(value) <= 20
        ):

            requested_ids.add(
                int(value)
            )

    # データベースに存在するユーザーだけを採用

    excluded_ids = set(

        User.objects.filter(
            pk__in=requested_ids
        ).values_list(
            "pk",
            flat=True,
        )

    )

    # =====================================================
    # Base queryset
    # =====================================================

    events = UsageEvent.objects.all()

    # =====================================================
    # Period filter
    # =====================================================

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
    # Exclude selected users
    # =====================================================

    if excluded_ids:

        events = events.exclude(
            user_id__in=excluded_ids
        )

    return (
        days,
        excluded_ids,
        events,
    )


# =========================================================
# App statistics
# =========================================================

def get_app_statistics(events):
    """
    アプリごとの利用状況を集計する。
    """

    local_date = TruncDate(
        "accessed_at",
        tzinfo=timezone.get_current_timezone(),
    )

    statistics = (

        events
        .values(
            "app_key"
        )
        .annotate(

            users=Count(
                "user_id",
                distinct=True,
            ),

            page_views=Count(
                "id"
            ),

            visits=Count(
                "id",
                filter=Q(
                    is_visit_start=True
                ),
            ),

            active_days=Count(
                local_date,
                distinct=True,
            ),

        )

    )

    statistics_map = {

        item["app_key"]: item

        for item in statistics

    }

    apps = []

    # 利用履歴がゼロのアプリも表示する

    for app_key, name in (
        UsageEvent.AppKey.choices
    ):

        item = statistics_map.get(
            app_key,
            {},
        )

        apps.append(
            {

                "key": app_key,

                "name": name,

                "users": item.get(
                    "users",
                    0,
                ),

                "page_views": item.get(
                    "page_views",
                    0,
                ),

                "visits": item.get(
                    "visits",
                    0,
                ),

                "active_days": item.get(
                    "active_days",
                    0,
                ),

            }
        )

    return apps


# =========================================================
# Dashboard
# =========================================================

@login_required
def dashboard(request):
    """
    管理ダッシュボード。

    全体・アプリ別・ユーザー別の
    利用状況を表示する。
    """

    # =====================================================
    # Permission
    # =====================================================

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied

    # =====================================================
    # Filters
    # =====================================================

    (
        days,
        excluded_ids,
        events,
    ) = get_period_events(
        request
    )

    # =====================================================
    # Target users
    # =====================================================

    target_users = User.objects.all()

    if excluded_ids:

        target_users = target_users.exclude(
            pk__in=excluded_ids
        )

    # =====================================================
    # Summary
    # =====================================================

    registered_users = (
        target_users.count()
    )

    active_users = (

        events
        .values(
            "user_id"
        )
        .distinct()
        .count()

    )

    total_page_views = (
        events.count()
    )

    total_visits = (

        events
        .filter(
            is_visit_start=True
        )
        .count()

    )

    # =====================================================
    # App statistics
    # =====================================================

    apps = get_app_statistics(
        events
    )

    # =====================================================
    # User statistics
    # =====================================================

    local_date = TruncDate(
        "accessed_at",
        tzinfo=timezone.get_current_timezone(),
    )

    user_statistics = (

        events
        .values(
            "user_id"
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

            active_days=Count(
                local_date,
                distinct=True,
            ),

            last_seen=Max(
                "accessed_at"
            ),

        )

    )

    statistics_map = {

        item["user_id"]: item

        for item in user_statistics

    }

    # =====================================================
    # Users included in statistics
    # =====================================================

    all_users = list(

        target_users.order_by(
            "username"
        )

    )

    # =====================================================
    # Nicknames
    # =====================================================

    profiles = {

        profile.user_id: profile

        for profile in (

            UserProfile.objects.filter(

                user_id__in=[
                    user.pk
                    for user in all_users
                ]

            )

        )

    }

    # =====================================================
    # User cards
    # =====================================================

    users = []

    for user in all_users:

        statistics = (
            statistics_map.get(
                user.pk,
                {},
            )
        )

        profile = profiles.get(
            user.pk
        )

        display_name = (
            profile.display_name
            if profile
            else user.username
        )

        users.append(
            {

                "id": user.pk,

                "username": (
                    user.username
                ),

                "display_name": (
                    display_name
                ),

                "page_views": (
                    statistics.get(
                        "page_views",
                        0,
                    )
                ),

                "visits": (
                    statistics.get(
                        "visits",
                        0,
                    )
                ),

                "active_days": (
                    statistics.get(
                        "active_days",
                        0,
                    )
                ),

                "last_seen": (
                    statistics.get(
                        "last_seen"
                    )
                ),

            }
        )

    # 閲覧数の多い順に表示

    users.sort(

        key=lambda item: (

            item["page_views"],

            item["active_days"],

        ),

        reverse=True,

    )

    # =====================================================
    # Context
    # =====================================================

    context = {

        "days": days,

        "excluded_ids": (
            sorted(excluded_ids)
        ),

        "registered_users": (
            registered_users
        ),

        "active_users": (
            active_users
        ),

        "total_page_views": (
            total_page_views
        ),

        "total_visits": (
            total_visits
        ),

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
    """
    集計対象の設定ページ。

    除外するユーザーを選択する。

    設定した条件はGETパラメータで
    ダッシュボードへ引き継ぐ。
    """

    # =====================================================
    # Permission
    # =====================================================

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied

    # =====================================================
    # Current filters
    # =====================================================

    (
        days,
        excluded_ids,
        _,
    ) = get_period_events(
        request
    )

    # =====================================================
    # All selectable users
    # =====================================================

    selectable_users = list(

        User.objects.all()
        .order_by(
            "username"
        )

    )

    # =====================================================
    # Nicknames
    # =====================================================

    profiles = {

        profile.user_id: profile

        for profile in (

            UserProfile.objects.filter(

                user_id__in=[
                    user.pk
                    for user in selectable_users
                ]

            )

        )

    }

    # =====================================================
    # Account selection
    # =====================================================

    exclusion_accounts = []

    for account in selectable_users:

        profile = profiles.get(
            account.pk
        )

        display_name = (
            profile.display_name
            if profile
            else account.username
        )

        exclusion_accounts.append(
            {

                "id": account.pk,

                "username": (
                    account.username
                ),

                "display_name": (
                    display_name
                ),

                "is_excluded": (
                    account.pk in excluded_ids
                ),

            }
        )

    # =====================================================
    # Context
    # =====================================================

    context = {

        "days": days,

        "excluded_ids": (
            sorted(excluded_ids)
        ),

        "exclusion_accounts": (
            exclusion_accounts
        ),

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
def user_detail(
    request,
    user_id,
):
    """
    ユーザー個別の利用状況を表示する。
    """

    # =====================================================
    # Permission
    # =====================================================

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied

    # =====================================================
    # Target user
    # =====================================================

    target_user = get_object_or_404(
        User,
        pk=user_id,
    )

    # =====================================================
    # Filters
    # =====================================================

    (
        days,
        excluded_ids,
        events,
    ) = get_period_events(
        request
    )

    # 除外対象のユーザーは詳細表示しない

    if target_user.pk in excluded_ids:
        raise Http404

    # =====================================================
    # Nickname
    # =====================================================

    profile = (

        UserProfile.objects
        .filter(
            user=target_user
        )
        .first()

    )

    display_name = (
        profile.display_name
        if profile
        else target_user.username
    )

    # =====================================================
    # User events
    # =====================================================

    events = events.filter(
        user=target_user
    )

    # =====================================================
    # Summary
    # =====================================================

    local_date = TruncDate(
        "accessed_at",
        tzinfo=timezone.get_current_timezone(),
    )

    summary = events.aggregate(

        page_views=Count(
            "id"
        ),

        visits=Count(
            "id",
            filter=Q(
                is_visit_start=True
            ),
        ),

        active_days=Count(
            local_date,
            distinct=True,
        ),

        last_seen=Max(
            "accessed_at"
        ),

    )

    # =====================================================
    # App statistics
    # =====================================================

    apps = get_app_statistics(
        events
    )

    # =====================================================
    # Context
    # =====================================================

    context = {

        "target_user": (
            target_user
        ),

        "display_name": (
            display_name
        ),

        "days": days,

        "excluded_ids": (
            sorted(excluded_ids)
        ),

        "summary": summary,

        "apps": apps,

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
@require_http_methods(
    ["GET", "POST"]
)
def access_control(request):
    """
    管理ダッシュボードの閲覧権限を設定する。

    Superuserのみ変更可能。
    """

    # =====================================================
    # Superuser only
    # =====================================================

    if not request.user.is_superuser:
        raise PermissionDenied

    # =====================================================
    # Save access settings
    # =====================================================

    if request.method == "POST":

        raw_ids = request.POST.getlist(
            "viewer_ids"
        )

        # IDの形式を検証

        if any(

            not (
                raw_id.isascii()
                and raw_id.isdecimal()
                and len(raw_id) <= 20
            )

            for raw_id in raw_ids

        ):

            return HttpResponseBadRequest(
                "Invalid user ID."
            )

        selected_ids = {

            int(raw_id)

            for raw_id in raw_ids

        }

        # 有効な一般ユーザーだけを対象にする

        selected_users = (

            User.objects.filter(

                pk__in=selected_ids,

                is_active=True,

                is_superuser=False,

            )

        )

        if (
            selected_users.count()
            != len(selected_ids)
        ):

            return HttpResponseBadRequest(
                "Invalid user selection."
            )

        # =================================================
        # Viewer group
        # =================================================

        group, _ = (

            Group.objects.get_or_create(
                name=VIEWER_GROUP_NAME
            )

        )

        # 閲覧可能ユーザーを更新

        group.user_set.set(
            selected_users
        )

        messages.success(
            request,
            "閲覧権限を更新しました。",
        )

        return redirect(
            "usage_analytics:access_control"
        )

    # =====================================================
    # Current viewer group
    # =====================================================

    group = (

        Group.objects.filter(
            name=VIEWER_GROUP_NAME
        )
        .first()

    )

    viewer_ids = set()

    if group:

        viewer_ids = set(

            group.user_set.values_list(
                "pk",
                flat=True,
            )

        )

    # =====================================================
    # Accounts
    # =====================================================

    users = list(

        User.objects.filter(

            is_active=True,

            is_superuser=False,

        )
        .order_by(
            "username"
        )

    )

    # =====================================================
    # Nicknames
    # =====================================================

    profiles = {

        profile.user_id: profile

        for profile in (

            UserProfile.objects.filter(

                user_id__in=[
                    user.pk
                    for user in users
                ]

            )

        )

    }

    # =====================================================
    # Account selection
    # =====================================================

    accounts = []

    for user in users:

        profile = profiles.get(
            user.pk
        )

        display_name = (
            profile.display_name
            if profile
            else user.username
        )

        accounts.append(
            {

                "id": user.pk,

                "username": (
                    user.username
                ),

                "display_name": (
                    display_name
                ),

                "is_viewer": (
                    user.pk in viewer_ids
                ),

            }
        )

    # =====================================================
    # Context
    # =====================================================

    context = {
        "accounts": accounts,
    }

    return render(
        request,
        "usage_analytics/access_control.html",
        context,
    )