from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.test import RequestFactory
from django.http import HttpResponse

from config import staging


def make_middleware(env):

    with mock.patch.dict(
        "os.environ",
        env,
    ):
        middleware = staging.StagingMiddleware(
            lambda request: HttpResponse("ok")
        )

    return middleware


@override_settings(SECRET_KEY="test-secret")
class StagingMiddlewareTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def call(self, middleware, request, env):

        with mock.patch.dict(
            "os.environ",
            env,
        ):
            return middleware(request)

    def test_production_is_untouched(self):

        env = {"APP_ENV": "", "STAGING_ACCESS_KEY": "k"}
        middleware = make_middleware(env)

        response = self.call(
            middleware,
            self.factory.get("/news/"),
            env,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Robots-Tag", response)

    def test_staging_requires_key_then_cookie(self):

        env = {"APP_ENV": "staging", "STAGING_ACCESS_KEY": "secret"}
        middleware = make_middleware(env)

        denied = self.call(
            middleware,
            self.factory.get("/news/"),
            env,
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied["X-Robots-Tag"], "noindex, nofollow")

        wrong = self.call(
            middleware,
            self.factory.get("/news/?staging_key=nope"),
            env,
        )

        self.assertEqual(wrong.status_code, 403)

        granted = self.call(
            middleware,
            self.factory.get("/news/?staging_key=secret&tab=x"),
            env,
        )

        self.assertEqual(granted.status_code, 302)
        self.assertEqual(granted["Location"], "/news/?tab=x")

        cookie = granted.cookies[staging.ACCESS_COOKIE].value
        self.assertNotEqual(cookie, "secret")

        request = self.factory.get("/news/")
        request.COOKIES[staging.ACCESS_COOKIE] = cookie

        allowed = self.call(middleware, request, env)

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed["X-Robots-Tag"], "noindex, nofollow")

    def test_pwa_files_are_open(self):

        env = {"APP_ENV": "staging", "STAGING_ACCESS_KEY": "secret"}
        middleware = make_middleware(env)

        response = self.call(
            middleware,
            self.factory.get("/service-worker.js"),
            env,
        )

        self.assertEqual(response.status_code, 200)
