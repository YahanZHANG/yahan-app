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
