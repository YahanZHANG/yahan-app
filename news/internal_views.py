import hmac
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
def refresh_news_internal(request):
    expected_token = os.environ.get(
        "NEWS_REFRESH_TOKEN",
        "",
    )

    provided_token = request.headers.get(
        "X-News-Refresh-Token",
        "",
    )

    if not expected_token:
        return JsonResponse(
            {
                "ok": False,
                "error": "NEWS_REFRESH_TOKEN is not configured.",
            },
            status=500,
        )

    if not hmac.compare_digest(
        provided_token,
        expected_token,
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "Unauthorized.",
            },
            status=403,
        )

    period = request.POST.get(
        "period",
        "",
    )

    if period not in {
        "morning",
        "afternoon",
    }:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid period.",
            },
            status=400,
        )

    manage_py = (
        Path(settings.BASE_DIR)
        / "manage.py"
    )

    log_path = Path(
        os.environ.get(
            "NEWS_REFRESH_LOG_PATH",
            "/var/data/news_refresh.log",
        )
    )

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        sys.executable,
        str(manage_py),
        "run_news_refresh",
        "--period",
        period,
    ]

    with open(
        log_path,
        "ab",
        buffering=0,
    ) as log_file:

        subprocess.Popen(
            command,
            cwd=settings.BASE_DIR,
            env=os.environ.copy(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    return JsonResponse(
        {
            "ok": True,
            "started": True,
            "period": period,
        },
        status=202,
    )