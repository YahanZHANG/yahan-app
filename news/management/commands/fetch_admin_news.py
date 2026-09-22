import re

from datetime import (
    datetime,
    timedelta,
)

import requests

from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import (
    Article,
    NewsSource,
)


LIST_URL = (
    "https://www.admin.ch/de/newnsb"
    "?display=list"
    "&newsCategoryIDs=all"
    "&publisherIDs=all"
    "&sort=dateDecreasing"
    "&topicIDs=all"
)


ARTICLE_URL_PATTERN = re.compile(
    r"^/de/newnsb/[^/?#]+$"
)


GERMAN_MONTHS = {
    "Januar": 1,
    "Februar": 2,
    "März": 3,
    "April": 4,
    "Mai": 5,
    "Juni": 6,
    "Juli": 7,
    "August": 8,
    "September": 9,
    "Oktober": 10,
    "November": 11,
    "Dezember": 12,
}


def clean_text(value):

    if not value:
        return ""

    return " ".join(
        value.split()
    )


def discover_article_urls(
    session,
    limit,
):
    """
    admin.chのニュース一覧から記事URLを取得する。
    """

    response = session.get(
        LIST_URL,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    urls = []
    seen = set()

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = link.get(
            "href",
            "",
        )

        if not ARTICLE_URL_PATTERN.match(
            href
        ):
            continue

        url = (
            "https://www.admin.ch"
            + href
        )

        if url in seen:
            continue

        seen.add(url)
        urls.append(url)

        if len(urls) >= limit:
            break

    return urls


def parse_german_date(text):
    """
    例：
    Veröffentlicht am 17. September 2026
    """

    match = re.search(
        (
            r"Veröffentlicht am\s+"
            r"(\d{1,2})\.\s+"
            r"([A-Za-zÄÖÜäöü]+)\s+"
            r"(\d{4})"
        ),
        text,
    )

    if not match:
        return None

    day = int(
        match.group(1)
    )

    month_name = (
        match.group(2)
    )

    year = int(
        match.group(3)
    )

    month = GERMAN_MONTHS.get(
        month_name
    )

    if not month:
        return None

    dt = datetime(
        year,
        month,
        day,
        12,
        0,
        0,
    )

    return timezone.make_aware(
        dt
    )


def parse_article(
    session,
    url,
):
    """
    admin.chの記事ページから
    タイトル・概要・公開日を取得する。
    """

    response = session.get(
        url,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    # ========================================
    # Title
    # ========================================

    h1 = soup.find("h1")

    if not h1:
        return None

    title = clean_text(
        h1.get_text(
            " ",
            strip=True,
        )
    )

    if not title:
        return None

    # ========================================
    # Published date
    # ========================================

    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    published_at = (
        parse_german_date(
            page_text
        )
        or timezone.now()
    )

    # ========================================
    # Summary
    # ========================================

    summary = ""

    description = soup.find(
        "meta",
        attrs={
            "name": "description",
        },
    )

    if description:

        summary = clean_text(
            description.get(
                "content",
                "",
            )
        )

    if not summary:

        main = soup.find(
            "main"
        )

        search_area = (
            main
            or soup
        )

        paragraphs = (
            search_area.find_all(
                "p"
            )
        )

        for paragraph in paragraphs:

            text = clean_text(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(text) >= 80:

                summary = text
                break

    summary = summary[:3000]

    return {
        "title": title,
        "summary": summary,
        "published_at": published_at,
    }


class Command(BaseCommand):

    help = (
        "Fetch latest news from "
        "Swiss Federal Administration."
    )

    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--limit",
            type=int,
            default=40,
        )

    def handle(
        self,
        *args,
        **options,
    ):

        limit = options[
            "limit"
        ]

        source = (
            NewsSource.objects.get(
                name=(
                    "Swiss Federal "
                    "Administration"
                )
            )
        )

        session = requests.Session()

        self.stdout.write(
            "Fetching admin.ch..."
        )

        try:

            urls = (
                discover_article_urls(
                    session,
                    limit,
                )
            )

        except requests.RequestException as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"List fetch failed: {exc}"
                )
            )

            session.close()
            return

        self.stdout.write(
            f"Found {len(urls)} article URLs "
            f"(limit: {limit})."
        )

        created_count = 0
        existing_count = 0
        skipped_count = 0
        error_count = 0

        cutoff = (
            timezone.now()
            - timedelta(days=7)
        )

        for index, url in enumerate(
            urls,
            start=1,
        ):

            if Article.objects.filter(
                source_url=url
            ).exists():

                existing_count += 1

                self.stdout.write(
                    f"[{index}/{len(urls)}] "
                    "existing"
                )

                continue

            try:

                data = parse_article(
                    session,
                    url,
                )

            except requests.RequestException as exc:

                error_count += 1

                self.stdout.write(
                    self.style.ERROR(
                        f"[{index}/{len(urls)}] "
                        f"ERROR: {exc}"
                    )
                )

                continue

            if not data:

                error_count += 1
                continue

            # ========================================
            # Skip old articles
            # ========================================

            if data["published_at"] < cutoff:

                skipped_count += 1
                continue

            # ========================================
            # Save
            # ========================================

            Article.objects.create(
                source=source,
                source_url=url,
                original_language="de",
                title_original=data[
                    "title"
                ],
                summary_original=data[
                    "summary"
                ],
                published_at=data[
                    "published_at"
                ],
            )

            created_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"[{index}/{len(urls)}] "
                    f"+ {data['title'][:90]}"
                )
            )

        session.close()

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Finished. "
                f"New: {created_count}, "
                f"Existing: {existing_count}, "
                f"Skipped: {skipped_count}, "
                f"Errors: {error_count}"
            )
        )