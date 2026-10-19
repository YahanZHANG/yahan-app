import os

import requests

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from news.services.news_sync import (
    import_payload,
)


class Command(BaseCommand):
    help = (
        "Copy recent news from production into this "
        "database (no OpenAI calls)."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--url",
            default=os.environ.get(
                "NEWS_PRODUCTION_URL",
                "",
            ),
            help=(
                "Production site URL, e.g. "
                "https://example.onrender.com "
                "(or set NEWS_PRODUCTION_URL)."
            ),
        )

        parser.add_argument(
            "--token",
            default=os.environ.get(
                "NEWS_REFRESH_TOKEN",
                "",
            ),
            help=(
                "Production NEWS_REFRESH_TOKEN "
                "(or set NEWS_REFRESH_TOKEN)."
            ),
        )

        parser.add_argument(
            "--days",
            type=int,
            default=7,
        )


    def handle(
        self,
        *args,
        **options,
    ):

        base_url = options["url"].rstrip("/")
        token = options["token"]

        if not base_url or not token:
            raise CommandError(
                "Set --url and --token "
                "(or NEWS_PRODUCTION_URL and NEWS_REFRESH_TOKEN)."
            )

        response = requests.get(
            f"{base_url}/news/internal/export/",
            params={
                "days": options["days"],
            },
            headers={
                "X-News-Refresh-Token": token,
            },
            timeout=60,
        )

        if response.status_code == 403:
            raise CommandError(
                "Production rejected the token."
            )

        response.raise_for_status()

        result = import_payload(
            response.json()
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"New: {result['created']}, "
                    f"Updated: {result['updated']}, "
                    f"Digests: {result['digests']}"
                )
            )
        )
