from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from news.models import Article, NewsDigest, NewsSource


@override_settings(
    STORAGES={
        "staticfiles": {
            "BACKEND": (
                "django.contrib.staticfiles.storage."
                "StaticFilesStorage"
            ),
        },
    },
)
class NewsTestCase(TestCase):

    def setUp(self):

        self.srf = NewsSource.objects.create(
            name="SRF",
            website_url="https://www.srf.ch",
            language="de",
        )

        self.rts = NewsSource.objects.create(
            name="RTS",
            website_url="https://www.rts.ch",
            language="fr",
        )

    def make_article(
        self,
        source,
        slug,
        processed=True,
        **kwargs,
    ):

        defaults = {
            "source": source,
            "source_url": f"https://example.com/{slug}",
            "original_language": source.language,
            "title_original": f"Original {slug}",
            "summary_original": f"Original summary {slug}",
            "title_ja": f"日本語 {slug}" if processed else "",
            "summary_ja": f"日本語要約 {slug}" if processed else "",
            "published_at": timezone.now(),
            "ai_processed_at": timezone.now() if processed else None,
        }

        defaults.update(kwargs)

        return Article.objects.create(
            **defaults
        )


class ArticleListTests(NewsTestCase):

    def test_duplicates_shown_once_with_all_sources(self):

        main = self.make_article(self.srf, "a")

        self.make_article(
            self.rts,
            "b",
            duplicate_of=main,
        )

        response = self.client.get(
            reverse("news:home")
        )

        self.assertContains(response, "日本語 a")
        self.assertNotContains(response, "日本語 b")
        self.assertContains(response, "SRF ほか1社")
        self.assertContains(response, "RTS")

    def test_untranslated_foreign_articles_are_hidden(self):

        self.make_article(
            self.srf,
            "pending",
            processed=False,
        )

        response = self.client.get(
            reverse("news:home")
        )

        self.assertNotContains(response, "Original pending")

    def test_source_page_includes_duplicates(self):

        main = self.make_article(self.srf, "a")

        self.make_article(
            self.rts,
            "b",
            duplicate_of=main,
        )

        response = self.client.get(
            reverse(
                "news:source_detail",
                args=[self.rts.id],
            )
        )

        self.assertContains(response, "日本語 b")

    def test_anonymous_original_language_shows_original_summary(self):

        self.make_article(self.srf, "a")

        session = self.client.session
        session["news_public_settings"] = {
            "display_language": "original",
        }
        session.save()

        response = self.client.get(
            reverse("news:home")
        )

        self.assertContains(response, "Original summary a")
        self.assertNotContains(response, "日本語要約 a")


class DedupeTests(NewsTestCase):

    def setUp(self):

        super().setUp()

        self.first = self.make_article(
            self.srf,
            "a",
            title_ja="来年の健康保険料、平均4.2%上昇へ　連邦政府が発表",
            summary_ja="スイス連邦政府は来年の健康保険料が平均で4.2%上昇すると発表した。",
            published_at=timezone.now() - timedelta(hours=2),
        )

        self.second = self.make_article(
            self.rts,
            "b",
            title_ja="連邦参事会、来年の健康保険料は平均4.2%上昇と発表",
            summary_ja="連邦参事会は、来年の健康保険料が平均4.2%上がると発表した。",
        )

        self.other = self.make_article(
            self.rts,
            "c",
            title_ja="バーゼルで住宅火災、けが人なし",
            summary_ja="バーゼルの住宅で火災が発生したが、けが人はいなかった。",
        )

    def test_similar_articles_are_merged_after_ai_check(self):

        with mock.patch(
            "news.services.deduplicator.confirm_same_event",
            return_value=True,
        ) as confirm:
            call_command(
                "dedupe_news",
                stdout=mock.MagicMock(),
            )

        for article in (self.first, self.second, self.other):
            article.refresh_from_db()
            self.assertIsNotNone(article.dedupe_checked_at)

        self.assertIsNone(self.first.duplicate_of)
        self.assertEqual(self.second.duplicate_of, self.first)
        self.assertIsNone(self.other.duplicate_of)

        # 似ていない記事（火災）は AI に聞かない
        confirm.assert_called_once()

    def test_ai_says_different(self):

        with mock.patch(
            "news.services.deduplicator.confirm_same_event",
            return_value=False,
        ):
            call_command(
                "dedupe_news",
                stdout=mock.MagicMock(),
            )

        self.second.refresh_from_db()

        self.assertIsNone(self.second.duplicate_of)

    def test_ai_error_retries_next_time(self):

        with mock.patch(
            "news.services.deduplicator.confirm_same_event",
            side_effect=RuntimeError("down"),
        ):
            call_command(
                "dedupe_news",
                stdout=mock.MagicMock(),
            )

        self.second.refresh_from_db()

        self.assertIsNone(self.second.dedupe_checked_at)

    def test_checked_articles_are_skipped(self):

        Article.objects.update(
            dedupe_checked_at=timezone.now(),
        )

        with mock.patch(
            "news.services.deduplicator.confirm_same_event",
        ) as confirm:
            call_command(
                "dedupe_news",
                stdout=mock.MagicMock(),
            )

        confirm.assert_not_called()


class AIClientTests(TestCase):

    SCHEMA = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    def test_openai_is_default(self):

        from config.services import ai_client

        response = SimpleNamespace(
            status="completed",
            output_text='{"ok": true}',
            usage=SimpleNamespace(input_tokens=10, output_tokens=2),
        )

        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=mock.MagicMock(return_value=response),
            )
        )

        with mock.patch.dict(
            "os.environ",
            {},
            clear=False,
        ), mock.patch(
            "config.services.openai_client.get_openai_client",
            return_value=client,
        ):
            import os
            os.environ.pop("AI_PROVIDER", None)

            result = ai_client.generate_json(
                "inst", "input", self.SCHEMA, "x", 100,
            )

        self.assertEqual(result.data, {"ok": True})
        self.assertEqual(result.model, "gpt-5.6-luna")

    def test_claude_when_switched(self):

        from config.services import ai_client

        response = SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text='{"ok": false}')],
            usage=SimpleNamespace(input_tokens=10, output_tokens=2),
        )

        client = SimpleNamespace(
            messages=SimpleNamespace(
                create=mock.MagicMock(return_value=response),
            )
        )

        with mock.patch.dict(
            "os.environ",
            {"AI_PROVIDER": "claude"},
        ), mock.patch.object(
            ai_client,
            "_claude_client",
            return_value=client,
        ):
            result = ai_client.generate_json(
                "inst", "input", self.SCHEMA, "x", 100,
            )

        self.assertEqual(result.data, {"ok": False})
        self.assertEqual(result.model, "claude-haiku-5-5")

        kwargs = client.messages.create.call_args.kwargs

        self.assertEqual(kwargs["system"], "inst")
        self.assertEqual(
            kwargs["output_config"]["format"]["schema"],
            self.SCHEMA,
        )

    def test_claude_cut_off_raises(self):

        from config.services import ai_client

        response = SimpleNamespace(
            stop_reason="max_tokens",
            content=[],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )

        client = SimpleNamespace(
            messages=SimpleNamespace(
                create=mock.MagicMock(return_value=response),
            )
        )

        with mock.patch.dict(
            "os.environ",
            {"AI_PROVIDER": "claude"},
        ), mock.patch.object(
            ai_client,
            "_claude_client",
            return_value=client,
        ):
            with self.assertRaises(RuntimeError):
                ai_client.generate_json(
                    "inst", "input", self.SCHEMA, "x", 100,
                )


class EnrichTests(NewsTestCase):

    def test_failed_articles_stop_retrying(self):

        article = self.make_article(
            self.srf,
            "a",
            processed=False,
        )

        with mock.patch(
            "news.management.commands.enrich_news.enrich_article",
            side_effect=RuntimeError("boom"),
        ) as enrich:

            for _ in range(5):
                call_command(
                    "enrich_news",
                    stdout=mock.MagicMock(),
                )

        article.refresh_from_db()

        self.assertEqual(enrich.call_count, 3)
        self.assertEqual(article.ai_attempts, 3)
        self.assertEqual(article.ai_error, "boom")


class FeaturedAndDayHeadingTests(NewsTestCase):

    def test_story_from_three_sources_is_featured(self):

        swi = NewsSource.objects.create(
            name="SWI",
            website_url="https://www.swissinfo.ch",
            language="en",
        )

        main = self.make_article(self.srf, "big")
        self.make_article(self.rts, "big2", duplicate_of=main)
        self.make_article(swi, "big3", duplicate_of=main)
        self.make_article(self.srf, "small")

        response = self.client.get(
            reverse("news:home")
        )

        featured = response.context["featured_articles"]

        self.assertEqual(
            [article.id for article in featured],
            [main.id],
        )
        self.assertContains(response, "注目ニュース")
        self.assertNotIn(
            main,
            list(response.context["articles"]),
        )

    def test_day_headings(self):

        self.make_article(self.srf, "today")
        self.make_article(
            self.srf,
            "yesterday",
            published_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(
            reverse("news:home")
        )

        self.assertContains(response, "今日")
        self.assertContains(response, "昨日")


class PushTests(NewsTestCase):

    def test_anonymous_user_can_subscribe_and_unsubscribe(self):

        from news.models import NewsPushSubscription

        endpoint = "https://fcm.googleapis.com/fcm/send/abc"

        response = self.client.post(
            reverse("news_push_subscribe"),
            data={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": "key",
                    "auth": "auth",
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            NewsPushSubscription.objects.filter(
                endpoint=endpoint,
                user__isnull=True,
            ).exists()
        )

        response = self.client.post(
            reverse("news_push_unsubscribe"),
            data={
                "endpoint": endpoint,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            NewsPushSubscription.objects.exists()
        )

    @override_settings(
        VAPID_PUBLIC_KEY="pub",
        VAPID_PRIVATE_KEY="priv",
        VAPID_CONTACT_EMAIL="a@example.com",
    )
    def test_push_is_sent_to_anonymous_subscribers_once(self):

        from news.models import NewsPushSubscription
        from news.push_sender import send_news_push_for_batch

        NewsPushSubscription.objects.create(
            endpoint="https://fcm.googleapis.com/fcm/send/x",
            p256dh="key",
            auth="auth",
        )

        with mock.patch(
            "news.push_sender.webpush"
        ) as webpush:

            first = send_news_push_for_batch(
                batch_key="2026-10-19-morning",
                new_articles_count=5,
                headline="見出し",
            )

            second = send_news_push_for_batch(
                batch_key="2026-10-19-morning",
                new_articles_count=5,
            )

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertIn(
            "ほか4件",
            webpush.call_args.kwargs["data"],
        )


class ArticleTextTests(NewsTestCase):

    def test_body_is_added_when_summary_is_short(self):

        from news.services.article_text import article_input_text

        article = self.make_article(
            self.srf,
            "short",
            processed=False,
            summary_original="Kurzer Teaser.",
        )

        html = (
            "<html><body><nav><p>Menu menu menu menu menu menu menu menu</p></nav>"
            "<article><p>Der Bundesrat hat heute entschieden, die Praemien zu senken.</p>"
            "<p>kurz</p>"
            "<p>Die Massnahme gilt ab Januar 2027 fuer alle Kantone der Schweiz.</p>"
            "</article></body></html>"
        )

        response = mock.Mock(text=html)
        response.raise_for_status = mock.Mock()

        with mock.patch(
            "news.services.article_text.requests.get",
            return_value=response,
        ):
            text = article_input_text(article)

        self.assertIn("Kurzer Teaser.", text)
        self.assertIn("Bundesrat hat heute", text)
        self.assertIn("Januar 2027", text)
        self.assertNotIn("Menu", text)
        self.assertNotIn("kurz\n", text)


@override_settings(
    ADMIN_NOTIFICATION_EMAIL="admin@example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AlertTests(NewsTestCase):

    def test_refresh_without_new_articles_sends_alert(self):

        from django.core import mail

        steps = [
            "fetch_news",
            "fetch_web_news",
            "fetch_admin_news",
            "cleanup_non_news",
            "cleanup_news",
            "classify_japanese_news",
            "enrich_news",
            "dedupe_news",
            "assign_news_regions",
            "generate_news_digest",
        ]

        def fake_call_command(name, **kwargs):
            self.assertIn(name, steps)

            if name == "fetch_web_news":
                raise RuntimeError("site changed")

        with mock.patch(
            "news.management.commands.refresh_news.call_command",
            side_effect=fake_call_command,
        ):
            call_command(
                "refresh_news",
                skip_push=True,
                stdout=mock.MagicMock(),
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("site changed", mail.outbox[0].body)
        self.assertIn("1件も取得できません", mail.outbox[0].body)


class AnnouncementTests(NewsTestCase):

    def test_latest_active_announcement_is_shown(self):

        from news.models import NewsAnnouncement

        NewsAnnouncement.objects.create(
            message="古いお知らせ",
        )
        NewsAnnouncement.objects.create(
            message="新しいお知らせ",
        )
        NewsAnnouncement.objects.create(
            message="非表示のお知らせ",
            is_active=False,
        )

        response = self.client.get(
            reverse("news:home")
        )

        self.assertContains(response, "新しいお知らせ")
        self.assertNotContains(response, "古いお知らせ")
        self.assertNotContains(response, "非表示のお知らせ")

    def test_old_announcement_is_hidden(self):

        from news.models import NewsAnnouncement

        announcement = NewsAnnouncement.objects.create(
            message="2週間以上前",
        )

        NewsAnnouncement.objects.filter(
            pk=announcement.pk,
        ).update(
            created_at=timezone.now() - timedelta(days=15),
        )

        response = self.client.get(
            reverse("news:home")
        )

        self.assertNotContains(response, "2週間以上前")


class CleanupTests(NewsTestCase):

    def test_old_articles_and_digests_are_deleted(self):

        old = timezone.now() - timedelta(days=8)

        self.make_article(self.srf, "old", published_at=old)
        self.make_article(self.srf, "new")

        for day, label in ((old, "old"), (timezone.now(), "new")):
            NewsDigest.objects.create(
                digest_date=day.date(),
                period="morning",
                summary_ja=label,
                source_from=day,
                source_to=day,
            )

        call_command("cleanup_news", stdout=mock.MagicMock())

        self.assertEqual(
            list(Article.objects.values_list("source_url", flat=True)),
            ["https://example.com/new"],
        )
        self.assertEqual(
            list(NewsDigest.objects.values_list("summary_ja", flat=True)),
            ["new"],
        )


class ShareAndOgpTests(NewsTestCase):

    def test_article_page_has_preview_and_share(self):

        article = self.make_article(self.srf, "a")

        response = self.client.get(
            reverse("news:article_detail", args=[article.pk])
        )

        self.assertContains(
            response,
            '<meta property="og:title" content="日本語 a">',
            html=False,
        )
        self.assertContains(response, "og-default")
        self.assertContains(response, "data-share-links")

    def test_duplicate_redirects_to_main_article(self):

        main = self.make_article(self.srf, "a")
        duplicate = self.make_article(self.rts, "b", duplicate_of=main)

        response = self.client.get(
            reverse("news:article_detail", args=[duplicate.pk])
        )

        self.assertRedirects(
            response,
            reverse("news:article_detail", args=[main.pk]),
        )

    def test_missing_article_shows_friendly_page(self):

        response = self.client.get(
            reverse("news:article_detail", args=[999])
        )

        self.assertEqual(response.status_code, 404)
        self.assertContains(
            response,
            "掲載期間が終わりました",
            status_code=404,
        )

    def test_home_cards_have_share_button(self):

        self.make_article(self.srf, "a")

        response = self.client.get(reverse("news:home"))

        self.assertContains(response, "news-share-button")
        self.assertContains(response, 'property="og:image"')


class LifeAlertTests(NewsTestCase):

    def setUp(self):

        super().setUp()

        from news.models import Region

        self.zurich = Region.objects.create(name="チューリッヒ", slug="zurich")
        self.bern = Region.objects.create(name="ベルン", slug="bern")
        self.swiss = Region.objects.create(name="スイス全国", slug="switzerland")

    def test_enrich_saves_life_alert(self):

        from config.services.ai_client import AIResult
        from news.services.ai_enricher import enrich_article

        article = self.make_article(self.srf, "a", processed=False)

        with mock.patch(
            "news.services.ai_enricher.generate_json",
            return_value=AIResult(
                data={
                    "title_ja": "SBBがスト",
                    "summary_ja": "要約",
                    "topics": [],
                    "life_alert": True,
                },
                model="m",
            ),
        ), mock.patch(
            "news.services.ai_enricher.article_input_text",
            return_value="text",
        ):
            enrich_article(article)

        article.refresh_from_db()

        self.assertTrue(article.life_alert)
        self.assertEqual(article.ai_model, "m")

    def test_life_page_filters_by_region(self):

        zurich = self.make_article(self.srf, "z", life_alert=True)
        zurich.regions.add(self.zurich)

        bern = self.make_article(self.srf, "b", life_alert=True)
        bern.regions.add(self.bern)

        national = self.make_article(self.srf, "n", life_alert=True)
        national.regions.add(self.swiss)

        self.make_article(self.srf, "x")

        response = self.client.get(
            reverse("news:life_alerts") + "?region=zurich"
        )

        self.assertContains(response, "日本語 z")
        self.assertContains(response, "日本語 n")
        self.assertNotContains(response, "日本語 b")
        self.assertNotContains(response, "日本語 x")

    def test_push_options_endpoint(self):

        from news.models import NewsPushSubscription

        subscription = NewsPushSubscription.objects.create(
            endpoint="https://push.example/1",
            p256dh="k",
            auth="a",
        )

        url = reverse("news_push_options")

        response = self.client.post(
            url,
            data={
                "endpoint": subscription.endpoint,
                "frequency": "daily",
                "alert_region": "zurich",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.json(),
            {"frequency": "daily", "alert_region": "zurich"},
        )

        # 全国は地域として選べない
        response = self.client.post(
            url,
            data={
                "endpoint": subscription.endpoint,
                "alert_region": "switzerland",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            url,
            data={"endpoint": "https://push.example/none"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    @override_settings(
        VAPID_PUBLIC_KEY="pub",
        VAPID_PRIVATE_KEY="priv",
        VAPID_CONTACT_EMAIL="a@example.com",
    )
    def test_scheduled_pushes_respect_frequency_and_region(self):

        from news.models import NewsPushSubscription
        from news.push_sender import send_scheduled_pushes

        started_at = timezone.now() - timedelta(minutes=5)

        every = NewsPushSubscription.objects.create(
            endpoint="https://push.example/every", p256dh="k", auth="a",
        )
        daily = NewsPushSubscription.objects.create(
            endpoint="https://push.example/daily", p256dh="k", auth="a",
            frequency="daily",
        )
        zurich_user = NewsPushSubscription.objects.create(
            endpoint="https://push.example/zurich", p256dh="k", auth="a",
            frequency="daily", alert_region=self.zurich,
        )
        bern_user = NewsPushSubscription.objects.create(
            endpoint="https://push.example/bern", p256dh="k", auth="a",
            frequency="daily", alert_region=self.bern,
        )

        alert = self.make_article(
            self.srf, "strike", life_alert=True,
            title_ja="チューリッヒでスト",
        )
        alert.regions.add(self.zurich)

        def sent_to(webpush):
            return [
                call.kwargs["subscription_info"]["endpoint"]
                for call in webpush.call_args_list
            ]

        with mock.patch("news.push_sender.webpush") as webpush:
            send_scheduled_pushes("afternoon", started_at)

        endpoints = sent_to(webpush)

        # 午後: 「更新のたび」と、チューリッヒの暮らしのお知らせだけ
        self.assertIn(every.endpoint, endpoints)
        self.assertIn(zurich_user.endpoint, endpoints)
        self.assertNotIn(daily.endpoint, endpoints)
        self.assertNotIn(bern_user.endpoint, endpoints)

        with mock.patch("news.push_sender.webpush") as webpush:
            send_scheduled_pushes("morning", started_at)

        endpoints = sent_to(webpush)

        # 朝: 1日1回の人にも届く
        self.assertIn(daily.endpoint, endpoints)
        self.assertIn(bern_user.endpoint, endpoints)


class CleanupPromotionTests(NewsTestCase):

    def test_surviving_duplicate_becomes_main(self):

        old = self.make_article(
            self.srf, "old",
            published_at=timezone.now() - timedelta(days=8),
        )
        newer = self.make_article(
            self.rts, "new",
            published_at=timezone.now() - timedelta(days=6),
            duplicate_of=old,
        )
        newest = self.make_article(
            self.rts, "newest",
            duplicate_of=old,
        )

        call_command("cleanup_news", stdout=mock.MagicMock())

        newer.refresh_from_db()
        newest.refresh_from_db()

        self.assertFalse(Article.objects.filter(pk=old.pk).exists())
        self.assertIsNone(newer.duplicate_of)
        self.assertEqual(newest.duplicate_of, newer)
