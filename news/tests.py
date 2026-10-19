from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from news.models import Article, NewsSource


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


def fake_embeddings(vectors):

    def create(**kwargs):

        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    embedding=vectors[text.split("\n")[0]]
                )
                for text in kwargs["input"]
            ]
        )

    return SimpleNamespace(
        embeddings=SimpleNamespace(
            create=create,
        )
    )


class DedupeTests(NewsTestCase):

    def test_similar_articles_are_merged(self):

        first = self.make_article(
            self.srf,
            "a",
            published_at=timezone.now() - timedelta(hours=2),
        )

        second = self.make_article(self.rts, "b")
        other = self.make_article(self.rts, "c")

        client = fake_embeddings({
            "日本語 a": [1.0, 0.0, 0.0],
            "日本語 b": [0.99, 0.05, 0.0],
            "日本語 c": [0.0, 0.0, 1.0],
        })

        with mock.patch(
            "news.services.deduplicator.get_openai_client",
            return_value=client,
        ):
            call_command(
                "dedupe_news",
                stdout=mock.MagicMock(),
            )

        first.refresh_from_db()
        second.refresh_from_db()
        other.refresh_from_db()

        self.assertIsNone(first.duplicate_of)
        self.assertEqual(second.duplicate_of, first)
        self.assertIsNone(other.duplicate_of)
        self.assertIsNotNone(other.embedding)

    def test_borderline_similarity_asks_ai(self):

        first = self.make_article(
            self.srf,
            "a",
            published_at=timezone.now() - timedelta(hours=2),
        )

        second = self.make_article(self.rts, "b")

        client = fake_embeddings({
            "日本語 a": [1.0, 0.0],
            "日本語 b": [0.8, 0.6],
        })

        with mock.patch(
            "news.services.deduplicator.get_openai_client",
            return_value=client,
        ), mock.patch(
            "news.services.deduplicator.confirm_same_event",
            return_value=False,
        ) as confirm:
            call_command(
                "dedupe_news",
                stdout=mock.MagicMock(),
            )

        second.refresh_from_db()

        confirm.assert_called_once()
        self.assertIsNone(second.duplicate_of)


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
