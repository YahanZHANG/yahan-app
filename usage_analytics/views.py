from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponseBadRequest
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

    events = UsageEvent.objects.all()

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

    return days, events


def get_app_statistics(events):

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

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied

    days, events = get_period_events(
        request
    )

    # ---------------------------------------------
    # Summary
    # ---------------------------------------------

    registered_users = (
        User.objects.count()
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

    # ---------------------------------------------
    # App statistics
    # ---------------------------------------------

    apps = get_app_statistics(
        events
    )

    # ---------------------------------------------
    # User statistics
    # ---------------------------------------------

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

    all_users = list(

        User.objects.all()
        .order_by(
            "username"
        )

    )

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

    users.sort(
        key=lambda item: (
            item["page_views"],
            item["active_days"],
        ),
        reverse=True,
    )

    context = {

        "days": days,

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
# User detail
# =========================================================

@login_required
def user_detail(
    request,
    user_id,
):

    if not can_view_analytics(
        request.user
    ):
        raise PermissionDenied

    target_user = get_object_or_404(
        User,
        pk=user_id,
    )

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

    days, events = get_period_events(
        request
    )

    events = events.filter(
        user=target_user
    )

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

    apps = get_app_statistics(
        events
    )

    context = {

        "target_user": (
            target_user
        ),

        "display_name": (
            display_name
        ),

        "days": days,

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

    # Only superusers may grant
    # or revoke analytics access.

    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":

        raw_ids = request.POST.getlist(
            "viewer_ids"
        )

        if any(
            not raw_id.isdecimal()
            for raw_id in raw_ids
        ):

            return HttpResponseBadRequest(
                "Invalid user ID."
            )

        selected_ids = {
            int(raw_id)
            for raw_id in raw_ids
        }

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

        group, _ = (
            Group.objects.get_or_create(
                name=VIEWER_GROUP_NAME
            )
        )

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

    # ---------------------------------------------
    # Current viewer group
    # ---------------------------------------------

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

    # ---------------------------------------------
    # Accounts
    # ---------------------------------------------

    accounts = []

    users = (

        User.objects.filter(

            is_active=True,

            is_superuser=False,

        )
        .order_by(
            "username"
        )

    )

    for user in users:

        profile = (

            UserProfile.objects.filter(
                user=user
            )
            .first()

        )

        accounts.append(
            {
                "id": user.pk,

                "username": (
                    user.username
                ),

                "display_name": (
                    profile.display_name
                    if profile
                    else user.username
                ),

                "is_viewer": (
                    user.pk in viewer_ids
                ),

            }
        )

    context = {
        "accounts": accounts,
    }

    return render(
        request,
        "usage_analytics/access_control.html",
        context,
    )