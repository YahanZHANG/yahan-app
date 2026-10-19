"""
テスト環境（ステージング）用の仕組み。

環境変数 APP_ENV=staging のときだけ有効になる。
本番では何もしない。

- STAGING_ACCESS_KEY を知っている人だけがサイトを見られる
  https://<テスト用URL>/?staging_key=<キー> を一度開くと
  Cookie が保存され、以後は普通に使える
- 全ページに「テスト環境」の帯を表示する
- 検索エンジンに載らないようにする
"""

import hashlib
import hmac
import os
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect


ACCESS_COOKIE = "yapp_staging_access"

ACCESS_PARAM = "staging_key"

# Cookieの有効期限（1年）
ACCESS_MAX_AGE = 365 * 24 * 60 * 60

# キーなしでも返すパス
# （PWAのアイコン・Service Worker・manifest）
OPEN_PATH_PREFIXES = (
    "/static/",
    "/service-worker.js",
    "/manifest.webmanifest",
    "/favicon.ico",
)


def is_staging():
    return (
        os.environ.get(
            "APP_ENV",
            "",
        ).lower()
        == "staging"
    )


def _access_key():
    return os.environ.get(
        "STAGING_ACCESS_KEY",
        "",
    )


def _cookie_value(key):
    """
    キーそのものではなく、署名した値をCookieに保存する。
    """

    return hmac.new(
        settings.SECRET_KEY.encode(),
        key.encode(),
        hashlib.sha256,
    ).hexdigest()


DENIED_HTML = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Yapp テスト環境</title>
</head>
<body style="font-family: sans-serif; padding: 40px 20px; text-align: center; color: #444;">
<h1 style="font-size: 1.2rem;">Yapp テスト環境</h1>
<p>このページは関係者専用です。</p>
</body>
</html>
"""


class StagingMiddleware:

    def __init__(
        self,
        get_response,
    ):

        self.get_response = get_response

        self.enabled = is_staging()


    def __call__(
        self,
        request,
    ):

        if not self.enabled:
            return self.get_response(
                request
            )

        key = _access_key()


        # -------------------------------------------------
        # アクセス制限
        # -------------------------------------------------

        if key and not request.path.startswith(
            OPEN_PATH_PREFIXES
        ):

            expected = _cookie_value(
                key
            )

            provided_key = request.GET.get(
                ACCESS_PARAM,
                "",
            )

            if provided_key and hmac.compare_digest(
                provided_key,
                key,
            ):

                # キーをURLから消してリダイレクト
                params = request.GET.copy()
                params.pop(ACCESS_PARAM, None)

                location = request.path

                if params:
                    location += "?" + urlencode(
                        params,
                        doseq=True,
                    )

                response = HttpResponseRedirect(
                    location
                )

                response.set_cookie(
                    ACCESS_COOKIE,
                    expected,
                    max_age=ACCESS_MAX_AGE,
                    secure=request.is_secure(),
                    httponly=True,
                    samesite="Lax",
                )

                return self._noindex(
                    response
                )

            cookie = request.COOKIES.get(
                ACCESS_COOKIE,
                "",
            )

            if not hmac.compare_digest(
                cookie,
                expected,
            ):

                return self._noindex(
                    HttpResponse(
                        DENIED_HTML,
                        status=403,
                    )
                )

        response = self.get_response(
            request
        )

        return self._noindex(
            response
        )


    def _noindex(
        self,
        response,
    ):

        response["X-Robots-Tag"] = "noindex, nofollow"

        return response


def staging_context(request):
    """
    テンプレートで {% if is_staging %} を使えるようにする。
    """

    return {
        "is_staging": is_staging(),
    }
