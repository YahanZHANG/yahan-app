import os

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.push_sender import (
    send_news_push_for_batch,
)
from news.services.deduplicator import (
    ready_articles,
)

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
            "--skip-push",
            action="store_true",
            help=(
                "Do not send push notifications "
                "after the refresh."
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
        # Push通知の新着件数はこの時刻以降に
        # 取得された記事で数える。
        # =====================================================

        started_at = timezone.now()

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
                "Swiss NEWS REFRESH"
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
            "1/10 Fetch RSS news",
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
            "2/10 Fetch webpage news",
            "fetch_web_news",
            limit=options["web_limit"],
        )


        # ========================================
        # 3. admin.ch
        # ========================================

        self._run_step(
            "3/10 Fetch admin.ch news",
            "fetch_admin_news",
            limit=options["admin_limit"],
        )


        # ========================================
        # 4. Remove ads / promotions
        # ========================================

        self._run_step(
            "4/10 Remove non-news content",
            "cleanup_non_news",
        )


        # ========================================
        # 5. Remove old articles
        #
        # OpenAI処理より先に実行。
        # ========================================

        self._run_step(
            "5/10 Remove old articles",
            "cleanup_news",
        )


        # ========================================
        # 6. Japanese local classification
        #
        # OpenAI APIは使用しない。
        # ========================================

        self._run_step(
            "6/10 Classify Japanese news",
            "classify_japanese_news",
        )


        # ========================================
        # 7. AI enrichment
        #
        # 外国語記事を日本語化し、
        # テーマ分類する。
        # ========================================

        self._run_step(
            "7/10 Translate and classify news",
            "enrich_news",
            limit=options["ai_limit"],
        )


        # ========================================
        # 8. Merge duplicates
        #
        # 同じ出来事を扱う記事を1つにまとめる。
        # ========================================

        self._run_step(
            "8/10 Merge duplicate news",
            "dedupe_news",
        )


        # ========================================
        # 9. Region classification
        #
        # このrefresh開始後に取得された
        # 新しい記事のみ地域分類する。
        #
        # OpenAI APIは使用しない。
        # ========================================

        self._run_step(
            "9/10 Classify news regions",
            "assign_news_regions",
        )


        # ========================================
        # 10. Digest
        # ========================================

        if options["skip_digest"]:

            self.stdout.write(
                ""
            )

            self.stdout.write(
                self.style.WARNING(
                    "10/10 News digest skipped."
                )
            )

        else:

            digest_options = {}


            if options["period"]:

                digest_options[
                    "period"
                ] = options["period"]


            self._run_step(
                "10/10 Generate news digest",
                "generate_news_digest",
                **digest_options,
            )


        # ========================================
        # Push notification
        #
        # 定時更新（periodあり）のときだけ送る。
        # 環境変数 NEWS_PUSH_ENABLED=true で有効化。
        # ========================================

        push_enabled = (
            os.environ.get(
                "NEWS_PUSH_ENABLED",
                "",
            ).lower()
            == "true"
        )

        if (
            options["period"]
            and push_enabled
            and not options["skip_push"]
        ):

            self._send_push(
                options["period"],
                started_at,
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


    def _send_push(
        self,
        period,
        started_at,
    ):

        self.stdout.write(
            ""
        )

        self.stdout.write(
            self.style.HTTP_INFO(
                "--- Send push notifications ---"
            )
        )

        try:

            new_articles_count = (
                ready_articles()
                .filter(
                    fetched_at__gte=started_at,
                    duplicate_of__isnull=True,
                )
                .count()
            )

            batch_key = (
                f"{timezone.localdate():%Y-%m-%d}"
                f"-{period}"
            )

            result = send_news_push_for_batch(
                batch_key=batch_key,
                new_articles_count=new_articles_count,
            )

            self.stdout.write(
                f"Push result: {result}"
            )

        except Exception as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"Push failed: {exc}"
                )
            )
