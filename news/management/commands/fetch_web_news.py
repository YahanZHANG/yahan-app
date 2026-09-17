import re
import requests

from news.services.japanese_classifier import (
    assign_japanese_topics,
)

from datetime import datetime
from urllib.parse import (
    urljoin,
    urlparse,
)

from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import (
    Article,
    NewsSource,
)

from news.services.content_filter import (
    should_skip_article,
)

SOURCE_CONFIG = {
    "20 Minuten": {
        "list_url": "https://www.20min.ch/schweiz",
        "language": "de",
        "article_pattern": re.compile(
            r"^/story/"
        ),
    },

    "Nau.ch": {
        "list_url": "https://www.nau.ch/news/schweiz",
        "language": "de",
        "article_pattern": re.compile(
            r"^/news/.+-\d+$"
        ),
    },

    "Watson": {
        "list_url": "https://www.watson.ch/schweiz/",
        "language": "de",
        "article_pattern": re.compile(
            r"^/[^/]+/[^/]+/\d+-"
        ),
    },

    "SWI swissinfo.ch": {
        "list_url": "https://www.swissinfo.ch/jpn/",
        "language": "ja",
        "swissinfo": True,
    },

    "Blick": {
        "list_url": "https://www.blick.ch/schweiz/",
        "language": "de",
        "article_pattern": re.compile(
            r"^/schweiz/.+-id\d+\.html$"
        ),
    },
}


HEADERS = {
    "Accept-Language":
        "de-DE,de;q=0.9,en;q=0.8",
}


SWI_EXCLUDED_TITLES = {
    "科学",
    "社会",
    "経済",
    "文化",
    "外交",
    "直接民主制",
    "ニュースレター",
}


def clean_text(value):
    if not value:
        return ""

    return " ".join(
        value.split()
    )


def parse_datetime(value):
    if not value:
        return None

    value = value.strip()

    try:

        if value.endswith("Z"):
            value = (
                value[:-1]
                + "+00:00"
            )

        dt = datetime.fromisoformat(
            value
        )

        if timezone.is_naive(dt):
            dt = timezone.make_aware(
                dt
            )

        return dt

    except ValueError:
        return None


def discover_urls(
    session,
    config,
    limit,
):
    response = session.get(
        config["list_url"],
        timeout=(5, 15),
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

        href = (
            link.get("href")
            or ""
        ).strip()

        text = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )


        # --------------------
        # SWI
        # --------------------

        if config.get(
            "swissinfo"
        ):

            if (
                "もっと読む"
                not in text
            ):
                continue

            display_title = (
                text
                .replace(
                    "もっと読む",
                    "",
                    1,
                )
                .strip()
            )

            if (
                not display_title
                or display_title
                in SWI_EXCLUDED_TITLES
            ):
                continue

            url = urljoin(
                config["list_url"],
                href,
            )


        # --------------------
        # Other sites
        # --------------------

        else:

            parsed = urlparse(
                href
            )

            path = (
                parsed.path
                if parsed.scheme
                else href.split("?")[0]
            )

            pattern = config[
                "article_pattern"
            ]

            if not pattern.search(
                path
            ):
                continue

            url = urljoin(
                config["list_url"],
                href,
            )


        if url in seen:
            continue

        seen.add(url)
        urls.append(url)


        if len(urls) >= limit:
            break


    return urls


def parse_article(
    session,
    url,
):
    response = session.get(
        url,
        timeout=(5, 15),
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )


    # --------------------
    # Title
    # --------------------

    title = ""

    og_title = soup.find(
        "meta",
        property="og:title",
    )

    if og_title:
        title = clean_text(
            og_title.get(
                "content",
                ""
            )
        )


    if not title:

        h1 = soup.find("h1")

        if h1:
            title = clean_text(
                h1.get_text(
                    " ",
                    strip=True,
                )
            )


    if not title:
        return None


    # --------------------
    # Short description
    # --------------------

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

        og_description = soup.find(
            "meta",
            property="og:description",
        )

        if og_description:

            summary = clean_text(
                og_description.get(
                    "content",
                    "",
                )
            )


    if not summary:

        main = (
            soup.find("article")
            or soup.find("main")
            or soup
        )

        for paragraph in main.find_all(
            "p"
        ):

            text = clean_text(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(text) >= 80:
                summary = text
                break


    # DBには記事全文を保存しない
    summary = summary[:1500]


    # --------------------
    # Published date
    # --------------------

    published_at = None

    published_meta = soup.find(
        "meta",
        property="article:published_time",
    )

    if published_meta:

        published_at = parse_datetime(
            published_meta.get(
                "content",
                ""
            )
        )


    if not published_at:

        time_tag = soup.find(
            "time",
            datetime=True,
        )

        if time_tag:

            published_at = parse_datetime(
                time_tag.get(
                    "datetime",
                    ""
                )
            )


    if not published_at:
        published_at = timezone.now()


    # --------------------
    # Canonical URL
    # --------------------

    canonical = soup.find(
        "link",
        rel="canonical",
    )

    if canonical:

        canonical_url = (
            canonical.get(
                "href",
                ""
            ).strip()
        )

        if canonical_url:
            url = canonical_url


    return {
        "url": url,
        "title": title,
        "summary": summary,
        "published_at": published_at,
    }


class Command(BaseCommand):
    help = (
        "Fetch news from public Swiss "
        "news webpages."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--limit",
            type=int,
            default=10,
        )


    def handle(
        self,
        *args,
        **options,
    ):

        limit = options["limit"]

        session = requests.Session()

        session.headers.update(
            HEADERS
        )


        total_new = 0
        total_existing = 0
        total_errors = 0


        for (
            source_name,
            config,
        ) in SOURCE_CONFIG.items():

            self.stdout.write("")
            self.stdout.write(
                f"Fetching: {source_name}"
            )


            try:

                source = (
                    NewsSource.objects.get(
                        name=source_name
                    )
                )

                try:

                    urls = discover_urls(
                        session,
                        config,
                        limit,
                    )

                except requests.RequestException as exc:

                    self.stdout.write(
                        self.style.ERROR(
                            f"{source_name}: failed to fetch list page: {exc}"
                        )
                    )

                    continue


            except Exception as exc:

                self.stdout.write(
                    self.style.ERROR(
                        f"List failed: {exc}"
                    )
                )

                total_errors += 1

                continue


            self.stdout.write(
                f"Found {len(urls)} URLs."
            )


            source_new = 0


            for index, url in enumerate(
                urls,
                start=1,
            ):

                if Article.objects.filter(
                    source_url=url
                ).exists():

                    total_existing += 1

                    continue


                try:

                    data = parse_article(
                        session,
                        url,
                    )


                except Exception as exc:

                    total_errors += 1

                    self.stdout.write(
                        self.style.ERROR(
                            (
                                f"  [{index}] "
                                f"ERROR: {exc}"
                            )
                        )
                    )

                    continue


                if not data:
                    total_errors += 1
                    continue

                if should_skip_article(
                    source_name=source_name,
                    title=data["title"],
                    summary=data["summary"],
                    url=data["url"],
                ):

                    self.stdout.write(
                        self.style.WARNING(
                            (
                                "  - skipped non-news: "
                                f"{data['title'][:90]}"
                            )
                        )
                    )

                    continue

                # canonical URLでも
                # 重複チェック
                if Article.objects.filter(
                    source_url=data["url"]
                ).exists():

                    total_existing += 1
                    continue


                language = config[
                    "language"
                ]


                if language == "ja":

                    title_ja = data[
                        "title"
                    ]

                    summary_ja = data[
                        "summary"
                    ]

                else:

                    title_ja = ""
                    summary_ja = ""


                article = Article.objects.create(
                    source=source,
                    source_url=data["url"],
                    original_language=language,
                    title_original=data[
                        "title"
                    ],
                    title_ja=title_ja,
                    summary_original=data[
                        "summary"
                    ],
                    summary_ja=summary_ja,
                    published_at=data[
                        "published_at"
                    ],
                )


                if language == "ja":

                    assign_japanese_topics(
                        article
                    )
                
                source_new += 1
                total_new += 1


                self.stdout.write(
                    self.style.SUCCESS(
                        (
                            f"  + "
                            f"{data['title'][:90]}"
                        )
                    )
                )


            self.stdout.write(
                (
                    f"{source_name}: "
                    f"{source_new} new"
                )
            )


        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Finished. "
                    f"New: {total_new}, "
                    f"Existing: "
                    f"{total_existing}, "
                    f"Errors: {total_errors}"
                )
            )
        )