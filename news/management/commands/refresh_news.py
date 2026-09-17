from django.core.management import (
    BaseCommand,
    call_command,
)


class Command(BaseCommand):
    help = (
        "Fetch, AI-process, and clean up "
        "Yahan News articles."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--feed-limit",
            type=int,
            default=10,
            help=(
                "Maximum number of RSS articles "
                "to inspect per source."
            ),
        )

        parser.add_argument(
            "--admin-limit",
            type=int,
            default=10,
            help=(
                "Maximum number of admin.ch "
                "articles to inspect."
            ),
        )

        parser.add_argument(
            "--ai-limit",
            type=int,
            default=100,
            help=(
                "Maximum number of new articles "
                "to AI-process."
            ),
        )


    def handle(
        self,
        *args,
        **options,
    ):

        feed_limit = options[
            "feed_limit"
        ]

        admin_limit = options[
            "admin_limit"
        ]

        ai_limit = options[
            "ai_limit"
        ]


        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=== Yahan News Refresh ==="
            )
        )


        # -------------------------
        # 1. RSS news
        # -------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_LABEL(
                "1/4 Fetching RSS news..."
            )
        )

        try:

            call_command(
                "fetch_news",
                limit=feed_limit,
            )

        except Exception as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"RSS fetch failed: {exc}"
                )
            )


        # -------------------------
        # 2. admin.ch
        # -------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_LABEL(
                "2/4 Fetching admin.ch..."
            )
        )

        try:

            call_command(
                "fetch_admin_news",
                limit=admin_limit,
            )

        except Exception as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"admin.ch fetch failed: {exc}"
                )
            )


        # -------------------------
        # 3. AI processing
        # -------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_LABEL(
                "3/4 AI processing..."
            )
        )

        try:

            call_command(
                "enrich_news",
                limit=ai_limit,
            )

        except Exception as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"AI processing failed: {exc}"
                )
            )


        # -------------------------
        # 4. Cleanup
        # -------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_LABEL(
                "4/4 Cleaning old articles..."
            )
        )

        try:

            call_command(
                "cleanup_news"
            )

        except Exception as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"Cleanup failed: {exc}"
                )
            )


        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "=== Yahan News refresh finished ==="
            )
        )