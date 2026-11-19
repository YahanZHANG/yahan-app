from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Article

from news.services.ai_enricher import (
    MAX_AI_ATTEMPTS,
    SUMMARY_VERSION,
    enrich_article,
)


# 古い書き方の要約を1回の更新で作り直す上限
# （新しい記事の翻訳を優先し、更新時間を延ばしすぎない）
RESUMMARIZE_LIMIT = 60

RESUMMARIZE_DAYS = 7


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


        # =====================================================
        # Only unprocessed articles by default
        # =====================================================

        if not force:

            queryset = queryset.filter(
                ai_processed_at__isnull=True,
                ai_attempts__lt=MAX_AI_ATTEMPTS,
            )


        articles = [
            (article, False)
            for article in queryset[:limit]
        ]


        # =====================================================
        # 古い書き方（長い要約）の記事を作り直す
        #
        # 一覧に出る代表記事だけ。新しい記事から順に。
        # =====================================================

        if not force:

            room = min(
                limit - len(articles),
                RESUMMARIZE_LIMIT,
            )

            if room > 0:

                old_style = (
                    Article.objects
                    .select_related(
                        "source"
                    )
                    .filter(
                        ai_processed_at__isnull=False,
                        summary_version__lt=SUMMARY_VERSION,
                        duplicate_of__isnull=True,
                        published_at__gte=(
                            timezone.now()
                            - timedelta(days=RESUMMARIZE_DAYS)
                        ),
                    )
                    .order_by(
                        "-published_at"
                    )
                )

                articles += [
                    (article, True)
                    for article in old_style[:room]
                ]


        if not articles:

            self.stdout.write(
                self.style.SUCCESS(
                    "No articles need AI processing."
                )
            )

            return


        success_count = 0
        error_count = 0


        # =====================================================
        # AI enrichment
        # =====================================================

        for index, (article, summary_only) in enumerate(
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
                    + (" (要約の作り直し)" if summary_only else "")
                )
            )

            self.stdout.write(
                article.title_original[:120]
            )


            try:

                result = enrich_article(
                    article,
                    summary_only=summary_only,
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

                if summary_only:

                    # 作り直しの失敗は、今の要約のまま次回やり直す
                    self.stdout.write(
                        self.style.ERROR(
                            f"ERROR: {exc}"
                        )
                    )

                    continue

                article.ai_error = str(
                    exc
                )[:2000]

                article.ai_attempts += 1

                article.save(
                    update_fields=[
                        "ai_error",
                        "ai_attempts",
                    ]
                )


                self.stdout.write(
                    self.style.ERROR(
                        f"ERROR: {exc}"
                    )
                )


        # =====================================================
        # Result
        # =====================================================

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