from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Article
from news.push_sender import (
    send_scheduled_pushes,
)
from news.services.alerts import (
    send_admin_alert,
)

# この件数以上の翻訳失敗があれば管理者に知らせる
UNTRANSLATED_ALERT_COUNT = 5


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

        self.failures = []

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
        # 7b. 暮らしのお知らせ（日本語の記事）
        #
        # 外国語の記事は翻訳のときに判定済み。
        # 日本語の記事だけ見出しと要約で判定する。
        # ========================================

        self._run_step(
            "7b/10 Mark life alerts (Japanese news)",
            "flag_life_alerts",
            days=1,
            japanese_only=True,
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
        # 通知を許可した端末にだけ届く。
        # ========================================

        if (
            options["period"]
            and not options["skip_push"]
        ):

            self._send_push(
                options["period"],
                started_at,
            )


        # ========================================
        # 異常があれば管理者にメール
        # ========================================

        self._check_health(
            started_at,
            options["period"],
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

            self.failures.append(
                f"{label}: {exc}"
            )

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

            result = send_scheduled_pushes(
                period,
                started_at,
            )

            self.stdout.write(
                f"Push result: {result}"
            )

        except Exception as exc:

            self.failures.append(
                f"Push通知: {exc}"
            )

            self.stdout.write(
                self.style.ERROR(
                    f"Push failed: {exc}"
                )
            )


    def _check_health(
        self,
        started_at,
        period,
    ):

        problems = list(
            self.failures
        )

        fetched = Article.objects.filter(
            fetched_at__gte=started_at,
        )

        if not fetched.exists():

            problems.append(
                "新しい記事が1件も取得できませんでした。"
                "ニュースソースのURLやRSSが変わった可能性があります。"
            )

        untranslated = (
            fetched
            .exclude(
                original_language="ja",
            )
            .filter(
                ai_processed_at__isnull=True,
            )
        )

        untranslated_count = untranslated.count()

        if untranslated_count >= UNTRANSLATED_ALERT_COUNT:

            sample_error = (
                untranslated
                .exclude(
                    ai_error="",
                )
                .values_list(
                    "ai_error",
                    flat=True,
                )
                .first()
            )

            problems.append(
                f"{untranslated_count}件の記事を翻訳できませんでした。"
                f"エラー例: {sample_error or '不明'}"
            )

        if not problems:
            return

        message = (
            f"ニュース更新（{period or '手動'}）で問題がありました。\n\n"
            + "\n".join(
                f"- {problem}"
                for problem in problems
            )
            + "\n\n詳細はサーバーのログ（news_refresh.log）を確認してください。"
        )

        self.stdout.write(
            self.style.WARNING(
                message
            )
        )

        send_admin_alert(
            "ニュース更新で問題が発生しました",
            message,
        )
