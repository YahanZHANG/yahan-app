from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Fetch, clean, classify, translate, "
        "assign regions, and summarize Swiss news."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--feed-limit",
            type=int,
            default=40,
            help=(
                "Maximum articles to inspect "
                "per RSS source."
            ),
        )

        parser.add_argument(
            "--web-limit",
            type=int,
            default=None,
            help=(
                "Override the individual webpage "
                "source limits. If omitted, use "
                "each source's configured limit."
            ),
        )

        parser.add_argument(
            "--admin-limit",
            type=int,
            default=40,
            help=(
                "Maximum admin.ch articles "
                "to inspect."
            ),
        )

        parser.add_argument(
            "--ai-limit",
            type=int,
            default=150,
            help=(
                "Maximum unprocessed foreign-language "
                "articles to send to OpenAI."
            ),
        )

        parser.add_argument(
            "--period",
            choices=[
                "morning",
                "late_morning",
                "afternoon",
                "evening",
            ],
            default=None,
            help=(
                "Force digest period. "
                "Normally provided by the scheduler."
            ),
        )

        parser.add_argument(
            "--skip-digest",
            action="store_true",
            help=(
                "Run refresh without generating "
                "a news digest."
            ),
        )


    def handle(
        self,
        *args,
        **options,
    ):

        # =====================================================
        # Refresh start time
        #
        # Region classification will only process articles
        # fetched after this timestamp.
        # =====================================================

        refresh_started_at = (
            timezone.now()
        )


        self.stdout.write(
            ""
        )

        self.stdout.write(
            self.style.SUCCESS(
                "========================================"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "YAHAN NEWS REFRESH"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "========================================"
            )
        )


        # ========================================
        # 1. RSS feeds
        # ========================================

        self._run_step(
            "1/9 Fetch RSS news",
            "fetch_news",
            limit=options["feed_limit"],
        )


        # ========================================
        # 2. Web sources
        #
        # 通常は媒体別の取得上限を使用。
        # --web-limit指定時のみ全媒体に
        # 同じ上限を適用。
        # ========================================

        self._run_step(
            "2/9 Fetch webpage news",
            "fetch_web_news",
            limit=options["web_limit"],
        )


        # ========================================
        # 3. admin.ch
        # ========================================

        self._run_step(
            "3/9 Fetch admin.ch news",
            "fetch_admin_news",
            limit=options["admin_limit"],
        )


        # ========================================
        # 4. Remove ads / promotions
        # ========================================

        self._run_step(
            "4/9 Remove non-news content",
            "cleanup_non_news",
        )


        # ========================================
        # 5. Remove old articles
        #
        # OpenAI処理より先に実行。
        # ========================================

        self._run_step(
            "5/9 Remove old articles",
            "cleanup_news",
        )


        # ========================================
        # 6. Japanese local classification
        #
        # OpenAI APIは使用しない。
        # ========================================

        self._run_step(
            "6/9 Classify Japanese news",
            "classify_japanese_news",
        )


        # ========================================
        # 7. AI enrichment
        #
        # 外国語記事を日本語化し、
        # テーマ分類する。
        # ========================================

        self._run_step(
            "7/9 Translate and classify news",
            "enrich_news",
            limit=options["ai_limit"],
        )


        # ========================================
        # 8. Region classification
        #
        # このrefresh開始後に取得された
        # 新しい記事のみ地域分類する。
        #
        # OpenAI APIは使用しない。
        # ========================================

        self._run_step(
            "8/9 Classify news regions",
            "assign_news_regions",
            since=(
                refresh_started_at
                .isoformat()
            ),
        )


        # ========================================
        # 9. Digest
        # ========================================

        if options["skip_digest"]:

            self.stdout.write(
                ""
            )

            self.stdout.write(
                self.style.WARNING(
                    "9/9 News digest skipped."
                )
            )

        else:

            digest_options = {}


            if options["period"]:

                digest_options[
                    "period"
                ] = options["period"]


            self._run_step(
                "9/9 Generate news digest",
                "generate_news_digest",
                **digest_options,
            )


        # ========================================
        # Finished
        # ========================================

        self.stdout.write(
            ""
        )

        self.stdout.write(
            self.style.SUCCESS(
                "========================================"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "NEWS REFRESH FINISHED"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "========================================"
            )
        )


    def _run_step(
        self,
        label,
        command_name,
        **kwargs,
    ):

        self.stdout.write(
            ""
        )

        self.stdout.write(
            self.style.HTTP_INFO(
                f"--- {label} ---"
            )
        )


        try:

            call_command(
                command_name,
                **kwargs,
            )


        except Exception as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"{command_name} failed: {exc}"
                )
            )

            self.stdout.write(
                self.style.WARNING(
                    "Continuing with next step."
                )
            )