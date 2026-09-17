from django.core.management.base import BaseCommand

from news.models import Article
from news.services.ai_enricher import (
    enrich_article,
)


class Command(BaseCommand):
    help = (
        "AI-process unprocessed news articles."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help=(
                "Maximum number of articles "
                "to process."
            ),
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Process articles again even "
                "if they were already AI-processed."
            ),
        )


    def handle(
        self,
        *args,
        **options,
    ):

        limit = options["limit"]
        force = options["force"]


        queryset = (
            Article.objects
            .select_related(
                "source"
            )
            .order_by(
                "-published_at"
            )
        )


        # 日本語記事は翻訳不要
        queryset = queryset.exclude(
            original_language="ja"
        )


        if not force:

            queryset = queryset.filter(
                ai_processed_at__isnull=True
            )


        articles = list(
            queryset[:limit]
        )


        if not articles:

            self.stdout.write(
                self.style.SUCCESS(
                    "No articles need AI processing."
                )
            )

            return


        success_count = 0
        error_count = 0


        for index, article in enumerate(
            articles,
            start=1,
        ):

            self.stdout.write(
                ""
            )

            self.stdout.write(
                (
                    f"[{index}/{len(articles)}] "
                    f"{article.source.name}"
                )
            )

            self.stdout.write(
                article.title_original[:120]
            )


            try:

                result = enrich_article(
                    article
                )

                success_count += 1


                self.stdout.write(
                    self.style.SUCCESS(
                        f"→ {result['title_ja']}"
                    )
                )


                if result["topics"]:

                    self.stdout.write(
                        "Themes: "
                        + ", ".join(
                            result["topics"]
                        )
                    )


                usage = result.get(
                    "usage"
                )

                if usage:

                    self.stdout.write(
                        (
                            "Tokens: "
                            f"{usage.input_tokens} input / "
                            f"{usage.output_tokens} output"
                        )
                    )


            except Exception as exc:

                error_count += 1

                article.ai_error = str(
                    exc
                )[:2000]

                article.save(
                    update_fields=[
                        "ai_error"
                    ]
                )


                self.stdout.write(
                    self.style.ERROR(
                        f"ERROR: {exc}"
                    )
                )


        self.stdout.write(
            ""
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Finished. "
                    f"Success: {success_count}, "
                    f"Errors: {error_count}"
                )
            )
        )