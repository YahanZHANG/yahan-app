import json

from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required

from django.http import JsonResponse

from django.shortcuts import redirect

from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from .models import NewsPushSubscription


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

@login_required
@require_POST
def subscribe(request):
    """
    ログイン中のユーザーの端末を
    Push通知の送信先として登録する。
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
    """
    ログイン中のユーザーの
    指定された端末の登録を解除する。
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

        user=request.user,

        endpoint=endpoint,

    ).delete()


    return JsonResponse(
        {
            "success": True,
        }
    )