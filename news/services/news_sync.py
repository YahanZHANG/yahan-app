"""
本番のニュースをローカル環境へコピーするための入出力。

本番: /news/internal/export/ が export_payload() を返す
ローカル: sync_news_from_production コマンドが import_payload() で取り込む

翻訳済みの日本語タイトル・要約もそのままコピーするので、
ローカルで OpenAI を使う必要はない。
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import (
    parse_date,
    parse_datetime,
)

from news.models import (
    Article,
    NewsDigest,
    NewsSource,
    Region,
    Topic,
)


SOURCE_FIELDS = [
    "name",
    "website_url",
    "feed_url",
    "language",
    "is_active",
    "display_order",
]

LABEL_FIELDS = [
    "name",
    "slug",
    "icon",
    "display_order",
    "is_active",
]

ARTICLE_FIELDS = [
    "source_url",
    "original_language",
    "title_original",
    "title_ja",
    "summary_original",
    "summary_ja",
    "is_featured",
    "ai_model",
    "ai_error",
    "life_alert",
]

DIGEST_FIELDS = [
    "period",
    "summary_ja",
    "highlights",
    "article_count",
    "ai_model",
    "input_tokens",
    "output_tokens",
]

MAX_DAYS = 14


def _pick(obj, fields):

    return {
        field: getattr(obj, field)
        for field in fields
    }


def _dt(value):

    return (
        value.isoformat()
        if value
        else None
    )


def export_payload(days=7):

    days = max(
        1,
        min(days, MAX_DAYS),
    )

    since = (
        timezone.now()
        - timedelta(days=days)
    )

    articles = (
        Article.objects
        .filter(
            published_at__gte=since,
        )
        .select_related(
            "source",
        )
        .prefetch_related(
            "topics",
            "regions",
        )
    )

    digests = NewsDigest.objects.filter(
        digest_date__gte=since.date(),
    )

    return {
        "exported_at": _dt(timezone.now()),
        "days": days,

        "sources": [
            _pick(source, SOURCE_FIELDS)
            for source in NewsSource.objects.all()
        ],

        "topics": [
            _pick(topic, LABEL_FIELDS)
            for topic in Topic.objects.all()
        ],

        "regions": [
            _pick(region, LABEL_FIELDS)
            for region in Region.objects.all()
        ],

        "articles": [
            {
                **_pick(article, ARTICLE_FIELDS),
                "source": article.source.name,
                "published_at": _dt(article.published_at),
                "fetched_at": _dt(article.fetched_at),
                "ai_processed_at": _dt(article.ai_processed_at),
                "topics": [
                    topic.slug
                    for topic in article.topics.all()
                ],
                "regions": [
                    region.slug
                    for region in article.regions.all()
                ],
            }
            for article in articles
        ],

        "digests": [
            {
                **_pick(digest, DIGEST_FIELDS),
                "digest_date": digest.digest_date.isoformat(),
                "source_from": _dt(digest.source_from),
                "source_to": _dt(digest.source_to),
            }
            for digest in digests
        ],
    }


@transaction.atomic
def import_payload(data):
    """
    本番のデータをローカルに上書き保存する。
    記事は source_url、ソースは name、テーマ・地域は slug で照合する。
    """

    sources = {}

    for item in data["sources"]:

        source, _ = NewsSource.objects.update_or_create(
            name=item["name"],
            defaults={
                key: value
                for key, value in item.items()
                if key != "name"
            },
        )

        sources[source.name] = source

    topics = {}

    for item in data["topics"]:

        topic, _ = Topic.objects.update_or_create(
            slug=item["slug"],
            defaults={
                key: value
                for key, value in item.items()
                if key != "slug"
            },
        )

        topics[topic.slug] = topic

    regions = {}

    for item in data["regions"]:

        region, _ = Region.objects.update_or_create(
            slug=item["slug"],
            defaults={
                key: value
                for key, value in item.items()
                if key != "slug"
            },
        )

        regions[region.slug] = region

    created = 0
    updated = 0

    for item in data["articles"]:

        # 古い本番データにない項目は飛ばす
        defaults = {
            field: item[field]
            for field in ARTICLE_FIELDS
            if field != "source_url"
            and field in item
        }

        defaults.update({
            "source": sources[item["source"]],
            "published_at": parse_datetime(item["published_at"]),
            "ai_processed_at": (
                parse_datetime(item["ai_processed_at"])
                if item["ai_processed_at"]
                else None
            ),
        })

        article, is_new = Article.objects.update_or_create(
            source_url=item["source_url"],
            defaults=defaults,
        )

        # fetched_at は auto_now_add なので別に更新する
        if item.get("fetched_at"):

            Article.objects.filter(
                pk=article.pk,
            ).update(
                fetched_at=parse_datetime(item["fetched_at"]),
            )

        article.topics.set([
            topics[slug]
            for slug in item["topics"]
            if slug in topics
        ])

        article.regions.set([
            regions[slug]
            for slug in item["regions"]
            if slug in regions
        ])

        if is_new:
            created += 1
        else:
            updated += 1

    for item in data["digests"]:

        NewsDigest.objects.update_or_create(
            digest_date=parse_date(item["digest_date"]),
            period=item["period"],
            defaults={
                **{
                    field: item[field]
                    for field in DIGEST_FIELDS
                    if field != "period"
                },
                "source_from": parse_datetime(item["source_from"]),
                "source_to": parse_datetime(item["source_to"]),
            },
        )

    return {
        "created": created,
        "updated": updated,
        "digests": len(data["digests"]),
    }
