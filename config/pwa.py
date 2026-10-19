from django.conf import settings

from django.contrib.staticfiles.storage import (
    staticfiles_storage,
)

from django.http import (
    FileResponse,
    JsonResponse,
)

from django.urls import (
    Resolver404,
    resolve,
)

from django.views.decorators.http import (
    require_GET,
    require_safe,
)


# =========================================================
# PWA Manifest
# =========================================================

def _start_url(request):

    """
    ホーム画面に追加したとき、追加したアプリ (例: /news/) から
    開くようにする。?start= の先頭のパスだけを使う。
    """

    path = request.GET.get("start", "")

    if not path.startswith("/") or path.startswith("//"):
        return "/"

    first = path.lstrip("/").split("/", 1)[0]

    if not first or not first.replace("-", "").replace("_", "").isalnum():
        return "/"

    # /accounts/ のようにトップページがないパスはポータルから開く
    if first in ("accounts", "password", "admin"):
        return "/"

    try:
        resolve(f"/{first}/")
    except Resolver404:
        return "/"

    return f"/{first}/"


@require_GET
def manifest(request):

    start_url = _start_url(request)

    data = {

        "id": start_url,

        "name": "Yapp",

        "short_name": "Yapp",

        "description": (
            "暮らしをよりよくするための情報やサービスをまとめたYapp"
        ),

        "start_url": start_url,

        "scope": "/",

        "display": "standalone",

        "background_color": "#F7F9FC",

        "theme_color": "#6577B6",

        "lang": "ja",

        "icons": [

            {
                "src": staticfiles_storage.url(
                    "pwa/icon-192.png"
                ),

                "sizes": "192x192",

                "type": "image/png",

                "purpose": "any",
            },

            {
                "src": staticfiles_storage.url(
                    "pwa/icon-512.png"
                ),

                "sizes": "512x512",

                "type": "image/png",

                "purpose": "any",
            },

            {
                "src": staticfiles_storage.url(
                    "pwa/icon-maskable.png"
                ),

                "sizes": "512x512",

                "type": "image/png",

                "purpose": "maskable",
            },

        ],

    }

    response = JsonResponse(

        data,

        content_type=(
            "application/manifest+json"
        ),

        json_dumps_params={
            "ensure_ascii": False,
        },

    )

    response["Cache-Control"] = (
        "no-cache"
    )

    return response


# =========================================================
# Favicon (/favicon.ico を直接取りに来るブラウザ向け)
# =========================================================

@require_safe
def favicon(request):

    response = FileResponse(

        open(
            settings.BASE_DIR / "static" / "pwa" / "favicon.ico",
            "rb",
        ),

        content_type="image/x-icon",

    )

    response["Cache-Control"] = "public, max-age=86400"

    return response


# =========================================================
# Service Worker
# =========================================================

@require_GET
def service_worker(request):

    file_path = (

        settings.BASE_DIR

        / "static"

        / "pwa"

        / "service-worker.js"

    )

    response = FileResponse(

        open(
            file_path,
            "rb",
        ),

        content_type=(
            "text/javascript; charset=utf-8"
        ),

    )

    response["Cache-Control"] = (
        "no-cache"
    )

    response["Service-Worker-Allowed"] = "/"

    return response