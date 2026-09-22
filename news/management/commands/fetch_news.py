from datetime import (
    datetime,
    timedelta,
    timezone as datetime_timezone,
)
from html import unescape

import feedparser
import requests

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import strip_tags

from news.models import (
    Article,
    NewsSource,
)

from news.services.classifier import (
    classify_article,
)

from news.services.content_filter import (
    should_skip_article,
)


USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; YahanNews/1.0)"
)


def clean_text(value):
    """
    RSS内のHTMLタグや余分な空白を除去する。
    """

    if not value:
        return ""

    value = strip_tags(value)
    value = unescape(value)

    return " ".join(
        value.split()
    )


def get_published_at(entry):
    """
    RSSの日付をtimezone aware datetimeに変換する。
    """

    date_fields = [
        "published_parsed",
        "updated_parsed",
        "created_parsed",
    ]

    for field in date_fields:

        value = entry.get(field)

        if value:

            return datetime(
                value.tm_year,
                value.tm_mon,
                value.tm_mday,
                value.tm_hour,
                value.tm_min,
                value.tm_sec,
                tzinfo=datetime_timezone.utc,
            )

    return timezone.now()


class Command(BaseCommand):

    help = (
        "Fetch articles from active RSS news sources."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--limit",
            type=int,
            default=40,
            help=(
                "Maximum number of entries "
                "to process per feed."
            ),
        )

    def handle(self, *args, **options):

        limit = options["limit"]

        sources = (
            NewsSource.objects
            .filter(
                is_active=True,
            )
            .exclude(
                feed_url="",
            )
            .order_by(
                "display_order",
            )
        )

        if not sources.exists():

            self.stdout.write(
                self.style.WARNING(
                    "No RSS sources configured."
                )
            )

            return

        total_created = 0
        total_existing = 0
        total_skipped = 0

        cutoff = (
            timezone.now()
            - timedelta(days=7)
        )

        for source in sources:

            self.stdout.write("")
            self.stdout.write(
                f"Fetching: {source.name}"
            )

            try:

                response = requests.get(
                    source.feed_url,
                    headers={
                        "User-Agent": USER_AGENT,
                    },
                    timeout=20,
                )

                response.raise_for_status()

            except requests.RequestException as exc:

                self.stdout.write(
                    self.style.ERROR(
                        f"Failed: {exc}"
                    )
                )

                continue

            feed = feedparser.parse(
                response.content
            )

            if feed.bozo:

                self.stdout.write(
                    self.style.WARNING(
                        "Feed contains parsing warnings."
                    )
                )

            entries = feed.entries[:limit]

            source_created = 0

            for entry in entries:

                source_url = (
                    entry.get("link")
                    or ""
                ).strip()

                title = clean_text(
                    entry.get(
                        "title",
                        "",
                    )
                )

                if not source_url or not title:

                    total_skipped += 1
                    continue

                published_at = get_published_at(
                    entry
                )

                # 7日より古い記事は取得しない

                if published_at < cutoff:

                    total_skipped += 1
                    continue

                summary = clean_text(
                    entry.get(
                        "summary",
                        "",
                    )
                    or entry.get(
                        "description",
                        "",
                    )
                )

                # 長い本文を保存しすぎない

                summary = summary[:2500]

                # 広告・宣伝等を除外

                if should_skip_article(
                    source_name=source.name,
                    title=title,
                    summary=summary,
                    url=source_url,
                ):

                    total_skipped += 1

                    self.stdout.write(
                        self.style.WARNING(
                            "  - skipped non-news: "
                            f"{title[:80]}"
                        )
                    )

                    continue

                # ========================================
                # Language
                # ========================================

                if source.language == "ja":

                    title_ja = title
                    summary_ja = summary
                    original_language = "ja"

                else:

                    title_ja = ""
                    summary_ja = ""

                    if source.language in {
                        "de",
                        "fr",
                        "it",
                        "en",
                    }:

                        original_language = (
                            source.language
                        )

                    else:

                        original_language = "other"

                # ========================================
                # Save
                # ========================================

                article, created = (
                    Article.objects
                    .get_or_create(
                        source_url=source_url,
                        defaults={
                            "source": source,
                            "original_language":
                                original_language,
                            "title_original":
                                title,
                            "title_ja":
                                title_ja,
                            "summary_original":
                                summary,
                            "summary_ja":
                                summary_ja,
                            "published_at":
                                published_at,
                        },
                    )
                )

                if created:

                    classify_article(
                        article
                    )

                    source_created += 1
                    total_created += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  + {title[:80]}"
                        )
                    )

                else:

                    total_existing += 1

            self.stdout.write(
                f"{source.name}: "
                f"{source_created} new"
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Finished. "
                f"New: {total_created}, "
                f"Existing: {total_existing}, "
                f"Skipped: {total_skipped}"
            )
        )