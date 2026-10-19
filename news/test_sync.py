import json
import os
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from news.models import Article, NewsDigest, NewsSource, Topic
from news.services.news_sync import export_payload, import_payload


class NewsSyncTests(TestCase):

    def setUp(self):

        self.source = NewsSource.objects.create(
            name="SRF",
            website_url="https://www.srf.ch",
            language="de",
        )

        self.topic = Topic.objects.create(
            name="政治",
            slug="politics",
        )

        self.article = Article.objects.create(
            source=self.source,
            source_url="https://www.srf.ch/a",
            original_language="de",
            title_original="Bundesrat",
            title_ja="連邦参事会",
            summary_ja="要約",
            published_at=timezone.now(),
            ai_processed_at=timezone.now(),
        )
        self.article.topics.add(self.topic)

        Article.objects.create(
            source=self.source,
            source_url="https://www.srf.ch/old",
            original_language="de",
            title_original="Old",
            published_at=timezone.now() - timedelta(days=30),
        )

        NewsDigest.objects.create(
            digest_date=timezone.localdate(),
            period="morning",
            summary_ja="まとめ",
            source_from=timezone.now(),
            source_to=timezone.now(),
        )

    def test_export_requires_token(self):

        with mock.patch.dict(os.environ, {"NEWS_REFRESH_TOKEN": "t"}):

            denied = self.client.get(reverse("news:internal_export"))

            allowed = self.client.get(
                reverse("news:internal_export"),
                HTTP_X_NEWS_REFRESH_TOKEN="t",
            )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)

        data = allowed.json()

        self.assertEqual(len(data["articles"]), 1)
        self.assertEqual(data["articles"][0]["title_ja"], "連邦参事会")

    def test_round_trip_into_empty_database(self):

        payload = json.loads(
            json.dumps(export_payload(days=7))
        )

        Article.objects.all().delete()
        NewsDigest.objects.all().delete()
        NewsSource.objects.all().delete()
        Topic.objects.all().delete()

        result = import_payload(payload)

        self.assertEqual(result["created"], 1)

        article = Article.objects.get()

        self.assertEqual(article.title_ja, "連邦参事会")
        self.assertIsNotNone(article.ai_processed_at)
        self.assertEqual(
            list(article.topics.values_list("slug", flat=True)),
            ["politics"],
        )
        self.assertEqual(NewsDigest.objects.count(), 1)

        # 2回目は更新になる
        result = import_payload(payload)

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)

    def test_command_uses_production_export(self):

        payload = json.loads(
            json.dumps(export_payload(days=7))
        )

        response = mock.Mock(status_code=200)
        response.json.return_value = payload

        with mock.patch(
            "news.management.commands.sync_news_from_production.requests.get",
            return_value=response,
        ) as get:
            call_command(
                "sync_news_from_production",
                url="https://prod.example.com/",
                token="t",
                stdout=mock.MagicMock(),
            )

        self.assertEqual(
            get.call_args.args[0],
            "https://prod.example.com/news/internal/export/",
        )
