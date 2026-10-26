from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from config.services.ai_client import (
    generate_json,
)

from news.services.ai_enricher import (
    LIFE_ALERT_RULES,
)

from news.services.deduplicator import (
    ready_articles,
)


BATCH_SIZE = 30

SUMMARY_CHARS = 300

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "life_alert_ids": {
            "type": "array",
            "items": {
                "type": "integer",
            },
        },
    },
    "required": [
        "life_alert_ids",
    ],
    "additionalProperties": False,
}

INSTRUCTIONS = """
スイス在住の日本人向けニュースアプリ「Swiss News」の編集者として、
番号付きのニュース一覧から「暮らしのお知らせ」に当たるものを選び、
その番号を life_alert_ids に入れてください。
当たるものがなければ空の配列にします。
""" + LIFE_ALERT_RULES


class Command(BaseCommand):
    help = (
        "Mark already translated articles as "
        "暮らしのお知らせ (life alerts) with one AI call "
        "per 30 articles. Uses only the Japanese title and summary."
    )

    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--days",
            type=int,
            default=3,
            help="Check articles published within this many days.",
        )

        parser.add_argument(
            "--japanese-only",
            action="store_true",
            help=(
                "Only Japanese source articles "
                "(the others are judged while translating)."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):

        articles = (
            ready_articles()
            .filter(
                duplicate_of__isnull=True,
                life_alert=False,
                published_at__gte=(
                    timezone.now()
                    - timedelta(days=options["days"])
                ),
            )
            .order_by(
                "-published_at",
            )
        )

        if options["japanese_only"]:

            articles = articles.filter(
                original_language="ja",
            )

        articles = list(
            articles
        )

        flagged = 0

        for start in range(
            0,
            len(articles),
            BATCH_SIZE,
        ):

            batch = articles[start:start + BATCH_SIZE]

            input_text = "\n\n".join(
                (
                    f"[{article.pk}] "
                    f"{article.title_ja or article.title_original}\n"
                    f"{(article.summary_ja or article.summary_original or '')[:SUMMARY_CHARS]}"
                )
                for article in batch
            )

            result = generate_json(
                instructions=INSTRUCTIONS,
                input_text=input_text,
                schema=OUTPUT_SCHEMA,
                name="life_alerts",
                max_tokens=300,
            )

            ids = {
                article.pk
                for article in batch
            } & set(
                result.data["life_alert_ids"]
            )

            for article in batch:

                if article.pk in ids:

                    article.life_alert = True

                    article.save(
                        update_fields=[
                            "life_alert",
                        ]
                    )

                    flagged += 1

                    self.stdout.write(
                        f"  [暮らし] {article.title_ja or article.title_original}"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Checked: {len(articles)}, Life alerts: {flagged}"
            )
        )
