from datetime import timedelta
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from travel.models import UserProfile

from .models import (
    OnlinePresence,
    UsageEvent,
)

from .permissions import can_view_analytics


# =========================================================
# Settings
# =========================================================

ONLINE_TIMEOUT_SECONDS = 20

APP_LABELS = dict(
    UsageEvent.AppKey.choices
)


# =========================================================
# Heartbeat receiver
# =========================================================

@login_required
@require_POST
def heartbeat(request):
    """
    ログイン中のユーザーのオンライン状態を更新。

    他ユーザーの情報は取得・変更できない。
    """

    # =====================================================
    # Validate app
    # =====================================================

    app_key = request.POST.get(
        "app_key",
        "",
    )

    if app_key not in APP_LABELS:

        return JsonResponse(
            {
                "error": "Invalid app.",
            },
            status=400,
        )

    # =====================================================
    # Validate tab ID
    # =====================================================

    raw_tab_id = request.POST.get(
        "tab_id",
        "",
    )

    try:

        if len(raw_tab_id) != 36:
            raise ValueError

        tab_id = UUID(
            raw_tab_id
        )

    except (ValueError, TypeError, AttributeError):

        return JsonResponse(
            {
                "error": "Invalid tab ID.",
            },
            status=400,
        )

    # =====================================================
    # Update online presence
    # =====================================================

    OnlinePresence.objects.update_or_create(

        user=request.user,

        tab_id=tab_id,

        defaults={
            "app_key": app_key,
            "last_seen": timezone.now(),
        },

    )

    # 成功時はデータを返さない
    return HttpResponse(
        status=204
    )


# =========================================================
# Online users API
# =========================================================

@login_required
@require_GET
@never_cache
def online_users(request):
    """
    オンラインと推定されるユーザーを取得。

    Superuserまたは閲覧権限のある
    ユーザーだけがアクセス可能。
    """

    # =====================================================
    # Permission
    # =====================================================

    if not can_view_analytics(
        request.user
    ):

        raise PermissionDenied

    # =====================================================
    # Online threshold
    # =====================================================

    now = timezone.now()

    cutoff = now - timedelta(
        seconds=ONLINE_TIMEOUT_SECONDS
    )

    # =====================================================
    # Get online presences
    # =====================================================

    presences = list(

        OnlinePresence.objects.filter(

            last_seen__gte=cutoff,

            user__is_active=True,

        )
        .select_related(
            "user"
        )
        .order_by(
            "-last_seen"
        )

    )

    # =====================================================
    # Nicknames
    # =====================================================

    user_ids = {

        presence.user_id

        for presence in presences

    }

    profiles = {

        profile.user_id: profile

        for profile in (

            UserProfile.objects.filter(
                user_id__in=user_ids
            )

        )

    }

    # =====================================================
    # Group by user
    # =====================================================

    users_map = {}

    for presence in presences:

        user_id = presence.user_id

        # ---------------------------------------------
        # First presence of this user
        # ---------------------------------------------

        if user_id not in users_map:

            profile = profiles.get(
                user_id
            )

            display_name = (

                profile.display_name

                if profile

                else presence.user.username

            )

            seconds_ago = max(

                0,

                int(
                    (
                        now
                        - presence.last_seen
                    ).total_seconds()
                ),

            )

            users_map[user_id] = {

                "id": user_id,

                "username": (
                    presence.user.username
                ),

                "display_name": (
                    display_name
                ),

                "last_seen": (

                    timezone.localtime(
                        presence.last_seen
                    ).isoformat()

                ),

                "seconds_ago": (
                    seconds_ago
                ),

                "apps": [],

            }

        # ---------------------------------------------
        # Add app
        # ---------------------------------------------

        user_data = users_map[
            user_id
        ]

        app_name = APP_LABELS.get(

            presence.app_key,

            presence.app_key,

        )

        if app_name not in user_data["apps"]:

            user_data["apps"].append(
                app_name
            )

    # =====================================================
    # Response
    # =====================================================

    users = list(
        users_map.values()
    )

    response = JsonResponse(
        {

            "count": len(users),

            "users": users,

            "online_window_seconds": (
                ONLINE_TIMEOUT_SECONDS
            ),

            "checked_at": (

                timezone.localtime(
                    now
                ).isoformat()

            ),

        }
    )

    response["Cache-Control"] = (
        "no-store"
    )

    return response