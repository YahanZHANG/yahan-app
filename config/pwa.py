from django.conf import settings

from django.contrib.staticfiles.storage import (
    staticfiles_storage,
)

from django.http import (
    FileResponse,
    JsonResponse,
)

from django.views.decorators.http import (
    require_GET,
)


# =========================================================
# PWA Manifest
# =========================================================

@require_GET
def manifest(request):

    data = {

        "id": "/",

        "name": "Yahan App",

        "short_name": "Yahan App",

        "description": (
            "スイスニュース・育児・暮らしを"
            "まとめたYahan App"
        ),

        "start_url": "/",

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