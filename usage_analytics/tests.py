import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .catalog import app_for_path
from .middleware import IGNORE_COOKIE, VISIT_COOKIE, VISITOR_COOKIE
from .models import AnalyticsExclusion, NewsSummaryRead, PageView
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


@override_settings(STORAGES=SIMPLE_STATIC)
class BehaviorAndChartTests(TestCase):

    def test_behavior_and_traffic_charts(self):

        import uuid
        from datetime import timedelta

        from django.utils import timezone

        from . import stats
        from .behavior import build_behavior

        now = timezone.now()

        # よく使う人: 3日来てコラムを見る
        regular = uuid.uuid4()
        for day in range(3):
            visit = uuid.uuid4()
            for path in ("/washoku/", "/washoku/columns/"):
                PageView.objects.create(visitor_id=regular, visit_id=visit, app_key="washoku", path=path,
                                        accessed_at=now - timedelta(days=day, minutes=5))

        # すぐ帰った人: 1回だけ、レシピ一覧で帰る
        for _ in range(2):
            PageView.objects.create(visitor_id=uuid.uuid4(), visit_id=uuid.uuid4(), app_key="washoku",
                                    path="/washoku/recipes/", accessed_at=now - timedelta(minutes=30))

        scope = stats.Scope(days=7)
        behavior = build_behavior(scope)

        self.assertEqual(behavior["regulars"], 1)
        self.assertEqual(behavior["short_visitors"], 2)
        self.assertEqual(behavior["exit_pages"][0]["path"], "/washoku/recipes/")
        self.assertEqual(behavior["exit_pages"][0]["title"], "レシピ一覧")
        self.assertTrue(behavior["advice"])

        traffic = stats.traffic_chart(scope)
        self.assertEqual(len(traffic["labels"]), 7)
        self.assertEqual(sum(traffic["series"][1]["values"]), 5)  # 訪問回数

        last_day = stats.last_day_chart(scope)
        self.assertEqual(len(last_day["labels"]), 96)
        self.assertEqual(sum(last_day["series"][0]["values"]), 3)  # 過去24時間に来た人 (15分ごと)

        User = get_user_model()
        self.client.force_login(User.objects.create_superuser("boss", "boss@example.com", "x"))
        response = self.client.get("/analytics/", HTTP_USER_AGENT=BROWSER)
        self.assertContains(response, "使い方の傾向と改善のヒント")
        self.assertContains(response, "過去24時間")


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES=SIMPLE_STATIC)
class NewsSummaryReadTests(TestCase):

    def setUp(self):

        from django.utils import timezone
        from news.models import Article, NewsSource

        source = NewsSource.objects.create(name="SRF", website_url="https://www.srf.ch", language="de")
        self.articles = [
            Article.objects.create(
                source=source,
                source_url=f"https://example.com/{n}",
                original_language="de",
                title_original=f"Original {n}",
                title_ja=f"日本語 {n}",
                published_at=timezone.now(),
            )
            for n in range(2)
        ]
        self.admin = get_user_model().objects.create_superuser("boss", "boss@example.com", "x")

    def send(self, reads):

        return self.client.post(
            "/analytics/news-reads/",
            data=json.dumps({"reads": reads}),
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

    def test_reads_are_saved_once_per_day_with_the_bigger_weight(self):

        first, second = self.articles
        self.client.get("/news/", HTTP_USER_AGENT=BROWSER)  # 訪問者 cookie

        self.assertEqual(self.send([{"id": first.pk, "w": 0.33}, {"id": 999999, "w": 1}]).status_code, 204)
        self.send([{"id": first.pk, "w": 1}, {"id": second.pk, "w": 0.25}])
        self.send([{"id": first.pk, "w": 0.5}])

        self.assertEqual(NewsSummaryRead.objects.count(), 2)
        self.assertEqual(NewsSummaryRead.objects.get(article_id=first.pk).weight, 1)
        self.assertEqual(NewsSummaryRead.objects.get(article_id=second.pk).weight, 0.25)

    def test_no_visitor_cookie_or_bad_body(self):

        self.assertEqual(self.send([{"id": self.articles[0].pk}]).status_code, 204)
        self.assertFalse(NewsSummaryRead.objects.exists())

        self.client.get("/news/", HTTP_USER_AGENT=BROWSER)
        self.assertEqual(self.send([{"id": "x"}]).status_code, 400)

    def test_dashboard_ranks_reads_and_clicks(self):

        first, second = self.articles
        self.client.get("/news/", HTTP_USER_AGENT=BROWSER)
        self.send([{"id": first.pk, "w": 1}, {"id": second.pk, "w": 0.5}])
        self.client.get(
            f"/analytics/public-news/articles/{second.pk}/click/?beacon=1",
            HTTP_USER_AGENT=BROWSER,
        )

        self.client.force_login(self.admin)
        response = self.client.get("/analytics/?app=news", HTTP_USER_AGENT=BROWSER)

        ranking = response.context["news_reads"]
        self.assertEqual([row["title"] for row in ranking], ["日本語 1", "日本語 0"])
        self.assertEqual((ranking[0]["reads"], ranking[0]["clicks"], ranking[0]["score"]), (0.5, 1, 3.5))
        self.assertContains(response, "要約がよく読まれた記事")

    def test_ranking_counts_only_the_last_three_days(self):

        import uuid
        from datetime import timedelta
        from django.utils import timezone
        from . import stats

        old = timezone.now() - timedelta(days=5)
        NewsSummaryRead.objects.create(
            visitor_id=uuid.uuid4(), article_id=self.articles[0].pk,
            article_title="古い", day=old.date(), read_at=old,
        )
        NewsSummaryRead.objects.create(
            visitor_id=uuid.uuid4(), article_id=self.articles[1].pk,
            article_title="新しい", day=timezone.localdate(),
        )

        self.assertEqual([row["title"] for row in stats.top_news_reads()], ["新しい"])
