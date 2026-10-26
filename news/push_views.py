import json

from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required

from django.http import JsonResponse

from django.shortcuts import redirect

from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from .models import (
    NewsPushSubscription,
    Region,
)


# =========================================================
# Old notification settings URL
# =========================================================

@login_required
@require_GET
def push_settings(request):
    """
    旧 /news/notifications/ から
    Newsの通常設定画面へ移動する。
    """

    return redirect(
        "news:settings"
    )


# =========================================================
# Parse subscription
# =========================================================

def parse_subscription(request):
    """
    ブラウザから送られたPush購読情報を検証する。
    """

    try:

        data = json.loads(
            request.body
        )

    except (
        ValueError,
        UnicodeDecodeError,
    ):

        return None

    if not isinstance(data, dict):
        return None


    # -----------------------------------------------------
    # Required fields
    # -----------------------------------------------------

    endpoint = data.get(
        "endpoint"
    )

    keys = data.get(
        "keys"
    )

    if not isinstance(endpoint, str):
        return None

    if not isinstance(keys, dict):
        return None

    p256dh = keys.get(
        "p256dh"
    )

    auth = keys.get(
        "auth"
    )

    if not all(
        isinstance(value, str)
        for value in (
            endpoint,
            p256dh,
            auth,
        )
    ):
        return None


    # -----------------------------------------------------
    # Length validation
    # -----------------------------------------------------

    if (
        not endpoint
        or not p256dh
        or not auth
        or len(endpoint) > 2048
        or len(p256dh) > 256
        or len(auth) > 256
    ):
        return None


    # -----------------------------------------------------
    # Trusted Push providers
    # -----------------------------------------------------

    try:

        parsed = urlsplit(
            endpoint
        )

        hostname = (
            parsed.hostname or ""
        ).lower()

        port = parsed.port

    except ValueError:

        return None

    trusted_endpoint = (

        hostname == "fcm.googleapis.com"

        or hostname == (
            "updates.push.services.mozilla.com"
        )

        or hostname == "push.apple.com"

        or hostname.endswith(
            ".push.apple.com"
        )

    )

    if (
        parsed.scheme != "https"
        or not trusted_endpoint
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return None


    # -----------------------------------------------------
    # Validated data
    # -----------------------------------------------------

    return {
        "endpoint": endpoint,
        "p256dh": p256dh,
        "auth": auth,
    }


# =========================================================
# Subscribe
# =========================================================

@require_POST
def subscribe(request):
    """
    端末をPush通知の送信先として登録する。
    未ログインのユーザーも登録できる。
    """

    data = parse_subscription(
        request
    )

    if data is None:

        return JsonResponse(

            {
                "error": "Invalid subscription.",
            },

            status=400,

        )


    NewsPushSubscription.objects.update_or_create(

        endpoint=data["endpoint"],

        defaults={

            "user": (
                request.user
                if request.user.is_authenticated
                else None
            ),

            "p256dh": data["p256dh"],

            "auth": data["auth"],

        },

    )


    return JsonResponse(
        {
            "success": True,
        }
    )


# =========================================================
# Unsubscribe
# =========================================================

@require_POST
def unsubscribe(request):
    """
    指定された端末の登録を解除する。
    endpoint は端末ごとに推測できないURLなので、
    それ自体を解除の鍵として扱う。
    """

    try:

        data = json.loads(
            request.body
        )

    except (
        ValueError,
        UnicodeDecodeError,
    ):

        return JsonResponse(

            {
                "error": "Invalid endpoint.",
            },

            status=400,

        )


    if not isinstance(data, dict):

        return JsonResponse(

            {
                "error": "Invalid endpoint.",
            },

            status=400,

        )


    endpoint = data.get(
        "endpoint"
    )

    if (
        not isinstance(endpoint, str)
        or not endpoint
        or len(endpoint) > 2048
    ):

        return JsonResponse(

            {
                "error": "Invalid endpoint.",
            },

            status=400,

        )


    NewsPushSubscription.objects.filter(

        endpoint=endpoint,

    ).delete()


    return JsonResponse(
        {
            "success": True,
        }
    )


# =========================================================
# Options (frequency / life alert region)
# =========================================================

# 暮らしのお知らせで選べない地域
NON_ALERT_REGION_SLUGS = {
    "switzerland",
    "other",
    "unknown",
}


def alert_regions():

    return (
        Region.objects
        .filter(
            is_active=True,
        )
        .exclude(
            slug__in=NON_ALERT_REGION_SLUGS,
        )
    )


@require_POST
def push_options(request):
    """
    この端末の通知の頻度と、暮らしのお知らせの地域を読む・変える。
    endpoint は端末ごとに推測できないURLなので、それを鍵にする。

    送るもの: {"endpoint": "...", "frequency"?: "every"|"daily",
              "alert_regions"?: ["<slug>", ...]}
    """

    try:

        data = json.loads(
            request.body
        )

    except (
        ValueError,
        UnicodeDecodeError,
    ):

        data = None

    if not isinstance(data, dict):

        return JsonResponse(
            {
                "error": "Invalid request.",
            },
            status=400,
        )

    endpoint = data.get(
        "endpoint"
    )

    if (
        not isinstance(endpoint, str)
        or not endpoint
        or len(endpoint) > 2048
    ):

        return JsonResponse(
            {
                "error": "Invalid endpoint.",
            },
            status=400,
        )

    subscription = (
        NewsPushSubscription.objects
        .filter(
            endpoint=endpoint,
        )
        .first()
    )

    if subscription is None:

        return JsonResponse(
            {
                "error": "Not subscribed.",
            },
            status=404,
        )

    update_fields = []

    frequency = data.get(
        "frequency"
    )

    if frequency is not None:

        if frequency not in dict(
            NewsPushSubscription.FREQUENCY_CHOICES
        ):

            return JsonResponse(
                {
                    "error": "Invalid frequency.",
                },
                status=400,
            )

        subscription.frequency = frequency

        update_fields.append(
            "frequency"
        )

    regions = None

    if "alert_regions" in data:

        slugs = data["alert_regions"]

        if (
            not isinstance(slugs, list)
            or not all(isinstance(slug, str) for slug in slugs)
        ):

            return JsonResponse(
                {
                    "error": "Invalid regions.",
                },
                status=400,
            )

        regions = list(
            alert_regions()
            .filter(
                slug__in=slugs,
            )
        )

        if len(regions) != len(set(slugs)):

            return JsonResponse(
                {
                    "error": "Invalid region.",
                },
                status=400,
            )

    if update_fields or regions is not None:

        subscription.save(
            update_fields=[
                *update_fields,
                "updated_at",
            ]
        )

    if regions is not None:

        subscription.alert_regions.set(
            regions
        )

    return JsonResponse(
        {
            "frequency": subscription.frequency,
            "alert_regions": sorted(
                subscription.alert_regions.values_list(
                    "slug",
                    flat=True,
                )
            ),
        }
    )
