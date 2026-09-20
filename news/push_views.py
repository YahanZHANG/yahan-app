import json

from urllib.parse import urlsplit

from django.conf import settings

from django.contrib.auth.decorators import login_required

from django.http import JsonResponse

from django.shortcuts import render

from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from .models import NewsPushSubscription


# =========================================================
# Settings page
# =========================================================

@login_required
@require_GET
def push_settings(request):

    return render(
        request,
        "news/push_settings.html",
        {
            "vapid_public_key": (
                settings.VAPID_PUBLIC_KEY
            ),
        },
    )


# =========================================================
# Parse subscription
# =========================================================

def parse_subscription(request):

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

    if (
        not endpoint
        or not p256dh
        or not auth
        or len(endpoint) > 2048
        or len(p256dh) > 256
        or len(auth) > 256
    ):
        return None

    # Allow trusted Web Push providers only.
    # This also prevents arbitrary server-side URLs
    # from being registered as push endpoints.

    parsed = urlsplit(
        endpoint
    )

    hostname = (
        parsed.hostname or ""
    ).lower()

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
        or parsed.port not in (None, 443)
    ):
        return None

    return {
        "endpoint": endpoint,
        "p256dh": p256dh,
        "auth": auth,
    }


# =========================================================
# Subscribe
# =========================================================

@login_required
@require_POST
def subscribe(request):

    data = parse_subscription(
        request
    )

    if data is None:

        return JsonResponse(
            {
                "error": (
                    "Invalid subscription."
                ),
            },
            status=400,
        )

    NewsPushSubscription.objects.update_or_create(

        endpoint=data["endpoint"],

        defaults={

            "user": request.user,

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

@login_required
@require_POST
def unsubscribe(request):

    try:

        data = json.loads(
            request.body
        )

        endpoint = data.get(
            "endpoint"
        )

    except (
        ValueError,
        UnicodeDecodeError,
        AttributeError,
    ):

        endpoint = None

    if not isinstance(endpoint, str):

        return JsonResponse(
            {
                "error": (
                    "Invalid endpoint."
                ),
            },
            status=400,
        )

    NewsPushSubscription.objects.filter(

        user=request.user,

        endpoint=endpoint,

    ).delete()

    return JsonResponse(
        {
            "success": True,
        }
    )