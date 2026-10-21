from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .catalog import app_for_path
from .middleware import IGNORE_COOKIE, VISIT_COOKIE, VISITOR_COOKIE
from .models import AnalyticsExclusion, PageView
from .sources import classify_source


SIMPLE_STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

BROWSER = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


class BrowserTests(TestCase):

    def test_in_app_browsers(self):

        from .browsers import detect_browser

        iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"

        self.assertEqual(detect_browser(iphone + " Mobile/15E148 Safari Line/13.19.0"), "line")
        self.assertEqual(detect_browser(iphone + " Mobile/21B91 [FBAN/FBIOS;FBAV/440.0.0.33.116]"), "facebook")
        self.assertEqual(detect_browser(iphone + " Mobile/15E148 Instagram 307.0.0.34.111"), "instagram")
        self.assertEqual(detect_browser(iphone + " Version/17.1 Mobile/15E148 Safari/604.1"), "safari")
        self.assertEqual(detect_browser(iphone + " CriOS/119.0 Mobile/15E148 Safari/604.1"), "chrome")
        self.assertEqual(detect_browser(iphone + " Mobile/15E148"), "ios_app")
        self.assertEqual(
            detect_browser("Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 Chrome/119.0 Mobile Safari/537.36"),
            "other_app",
        )


class SourceTests(TestCase):

    def test_known_hosts(self):

        self.assertEqual(classify_source("www.google.co.jp"), ("search", "Google"))
        self.assertEqual(classify_source("l.instagram.com"), ("social", "Instagram"))
        self.assertEqual(classify_source("jp.naver.line.android"), ("messaging", "LINE"))
        self.assertEqual(classify_source("www.reddit.com"), ("social", "Reddit"))
        self.assertEqual(classify_source("example.ch"), ("referral", "example.ch"))

    def test_utm_and_direct(self):

        self.assertEqual(classify_source("www.google.com", "instagram"), ("campaign", "instagram"))
        self.assertEqual(classify_source(""), ("direct", "直接"))
        self.assertEqual(
            classify_source("yahan-app.onrender.com", own_hosts={"yahan-app.onrender.com"}),
            ("direct", "直接"),
        )

    def test_app_for_path(self):

        self.assertEqual(app_for_path("/"), "portal")
        self.assertEqual(app_for_path("/accounts/login/"), "portal")
        self.assertEqual(app_for_path("/washoku/recipes/3/"), "washoku")
        self.assertEqual(app_for_path("/newapp/"), "newapp")


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES=SIMPLE_STATIC)
class TrackingTests(TestCase):

    def get(self, path, **extra):

        return self.client.get(path, HTTP_USER_AGENT=BROWSER, **extra)

    def test_records_any_app_with_source(self):

        response = self.get("/washoku/", HTTP_REFERER="https://www.google.ch/search?q=x")

        self.assertEqual(response.status_code, 200)
        view = PageView.objects.get()
        self.assertEqual(view.app_key, "washoku")
        self.assertTrue(view.is_visit_start)
        self.assertTrue(view.is_new_visitor)
        self.assertEqual((view.source_type, view.source_label), ("search", "Google"))
        self.assertEqual(view.browser, "safari")
        self.assertIn(VISITOR_COOKIE, response.cookies)
        self.assertIn(VISIT_COOKIE, response.cookies)

    def test_same_visit_continues(self):

        self.get("/washoku/")
        self.get("/outings/", HTTP_REFERER="http://testserver/washoku/")

        first, second = PageView.objects.order_by("id")
        self.assertEqual(first.visit_id, second.visit_id)
        self.assertEqual(first.visitor_id, second.visitor_id)
        self.assertFalse(second.is_visit_start)
        self.assertFalse(second.is_new_visitor)
        self.assertEqual(second.source_type, "")

    def test_skips_bots_admin_pages_and_ignored_browser(self):

        self.client.get("/washoku/", HTTP_USER_AGENT="Googlebot/2.1")
        self.client.get("/washoku/")
        self.get("/analytics/")
        self.get("/news/internal/export/")

        self.client.cookies[IGNORE_COOKIE] = "1"
        self.get("/washoku/")

        self.assertFalse(PageView.objects.exists())


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES=SIMPLE_STATIC)
class DashboardTests(TestCase):

    def setUp(self):

        User = get_user_model()
        self.admin = User.objects.create_superuser("boss", "boss@example.com", "x")
        self.member = User.objects.create_user("member", "member@example.com", "x")

    def visit(self, path, **extra):

        return self.client.get(path, HTTP_USER_AGENT=BROWSER, **extra)

    def test_only_viewers_can_open(self):

        self.client.force_login(self.member)
        self.assertEqual(self.visit("/analytics/").status_code, 403)

    def test_dashboard_pages_render(self):

        self.visit("/washoku/", HTTP_REFERER="https://l.instagram.com/")
        self.visit("/news/?utm_source=line&utm_campaign=test")
        visitor_id = PageView.objects.first().visitor_id

        self.client.cookies.clear()
        self.client.force_login(self.admin)

        for url in (
            "/analytics/",
            "/analytics/?days=7",
            "/analytics/?days=365",
            "/analytics/?app=washoku",
            "/analytics/?app=unknown-app",
            "/analytics/settings/",
            f"/analytics/visitors/{visitor_id}/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.visit(url).status_code, 200)

        response = self.visit("/analytics/")
        self.assertContains(response, "Instagram")
        self.assertContains(response, "最近の傾向")

    def test_excluded_account_hides_its_browser(self):

        self.client.force_login(self.member)
        self.visit("/washoku/")
        visitor_cookie = self.client.cookies[VISITOR_COOKIE].value
        self.client.logout()  # テスト用 Client は cookie も消すので戻す
        self.client.cookies[VISITOR_COOKIE] = visitor_cookie
        self.visit("/outings/")  # 同じブラウザでログアウト中

        AnalyticsExclusion.objects.create(user=self.member)

        self.client.force_login(self.admin)
        response = self.visit("/analytics/")

        self.assertEqual(response.context["data"]["summary"]["visitors"], 0)


    def test_live_status_counts_anonymous_visitors(self):

        self.visit("/washoku/")
        self.client.cookies.clear()
        self.visit("/outings/")
        self.client.cookies.clear()

        self.client.force_login(self.admin)
        response = self.visit("/analytics/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["live"]["visitors"], 2)
        self.assertEqual(response.context["live"]["anonymous"], 2)
        self.assertContains(response, "見ている人がいます")
