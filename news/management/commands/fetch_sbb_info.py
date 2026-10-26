"""
SBB の運行情報（data.sbb.ch の rail-traffic-information、APIキー不要）から、
まだ続いている大きめの運休・遅延・工事だけを記事として取り込む。

短いトラブル（すぐ復旧するもの）は1日4回の更新では間に合わないので取らない。
取り込んだ記事は翻訳のときに必ず「暮らしのお知らせ」になる。
"""

import hashlib
from datetime import timedelta

import requests

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags

from news.models import (
    Article,
    NewsSource,
)


API_URL = (
    "https://data.sbb.ch/api/explore/v2.1/catalog/datasets/"
    "rail-traffic-information/records"
)

SOURCE_NAME = "SBB 運行情報"

SOURCE_URL = (
    "https://www.sbb.ch/de/fahrplan/bahnverkehrsinformation.html"
)

USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; YahanNews/1.0)"
)

# これより短いトラブルは取り込まない
MIN_DURATION = timedelta(hours=2)

# 1回の更新で取り込む最大件数（翻訳の費用を抑える）
MAX_NEW = 8


def get_source():

    source, _ = NewsSource.objects.get_or_create(
        name=SOURCE_NAME,
        defaults={
            "website_url": SOURCE_URL,
            "language": "de",
            "display_order": 100,
        },
    )

    return source


def _text(value):

    value = (value or "").replace(
        "<br />", "\n"
    ).replace(
        "<br>", "\n"
    )

    return "\n".join(
        " ".join(line.split())
        for line in strip_tags(value).splitlines()
        if line.strip()
    )


def is_relevant(record, now):
    """
    まだ終わっていない、2時間以上続く運行情報か。
    """

    start = parse_datetime(
        record.get("startdatetime") or ""
    )

    end = parse_datetime(
        record.get("enddatetime") or ""
    )

    if end is not None and end < now:
        return False

    if start is not None and end is not None:
        return end - start >= MIN_DURATION

    # 終わりが決まっていない = 復旧の見通しが立っていない
    return True


def record_url(record):
    """
    記事ごとに一意のURL。SBB のリンクは共通ページのことがあるので印を付ける。
    """

    key = hashlib.sha1(
        "|".join([
            record.get("title") or "",
            record.get("startdatetime") or "",
        ]).encode()
    ).hexdigest()[:12]

    link = record.get("link") or SOURCE_URL

    return f"{link.split('#')[0]}#sbb-{key}"


class Command(BaseCommand):
    help = (
        "Fetch longer, still active disruptions "
        "from SBB rail traffic information."
    )

    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Records to read from the SBB API.",
        )

    def handle(
        self,
        *args,
        **options,
    ):

        source = get_source()

        if not source.is_active:

            self.stdout.write(
                "SBB source is turned off in admin. Skipping."
            )

            return

        response = requests.get(
            API_URL,
            params={
                "order_by": "published desc",
                "limit": min(options["limit"], 100),
            },
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=20,
        )

        response.raise_for_status()

        now = timezone.now()

        created = 0

        for record in response.json().get("results", []):

            if created >= MAX_NEW:
                break

            title = _text(
                record.get("title")
            )

            if not title or not is_relevant(record, now):
                continue

            published_at = (
                parse_datetime(record.get("published") or "")
                or now
            )

            if published_at < now - timedelta(days=2):
                continue

            start = (record.get("startdatetime") or "")[:16].replace("T", " ")
            end = (record.get("enddatetime") or "")[:16].replace("T", " ")

            summary = _text(
                record.get("description")
            )

            if start or end:
                summary += f"\n\nGültig: {start} – {end or 'offen'}"

            article, is_new = Article.objects.get_or_create(
                source_url=record_url(record),
                defaults={
                    "source": source,
                    "original_language": "de",
                    "title_original": title[:500],
                    "summary_original": summary[:2500],
                    "published_at": published_at,
                },
            )

            if is_new:

                created += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  + {title[:80]}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"SBB: {created} new"
            )
        )
