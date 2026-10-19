from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.services.deduplicator import (
    WINDOW,
    embed_articles,
    find_duplicate_root,
    ready_articles,
)


class Command(BaseCommand):
    help = (
        "Group articles about the same event "
        "so they are shown once with all sources."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help=(
                "Only check articles published "
                "within this many days."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show detected duplicates "
                "without saving anything."
            ),
        )

        parser.add_argument(
            "--no-ai",
            action="store_true",
            help=(
                "Use only embedding similarity "
                "(no AI confirmation)."
            ),
        )


    def handle(
        self,
        *args,
        **options,
    ):

        dry_run = options["dry_run"]

        since = (
            timezone.now()
            - timedelta(days=options["days"])
        )

        recent = (
            ready_articles()
            .filter(
                published_at__gte=since - WINDOW,
            )
            .select_related(
                "source",
                "duplicate_of",
            )
            .order_by(
                "published_at",
                "id",
            )
        )

        # 埋め込みがない記事 = まだ重複チェックしていない記事
        new_articles = [
            article
            for article in recent
            if article.embedding is None
            and article.published_at >= since
        ]

        candidates = [
            article
            for article in recent
            if article.embedding is not None
        ]

        if not new_articles:

            self.stdout.write(
                self.style.SUCCESS(
                    "No new articles to check."
                )
            )

            return

        embed_articles(
            new_articles,
            save=not dry_run,
        )

        merged = 0

        for article in new_articles:

            root, score = find_duplicate_root(
                article,
                candidates,
                use_ai=not options["no_ai"],
            )

            if root is not None:

                merged += 1

                self.stdout.write(
                    (
                        f"  = [{score:.2f}] "
                        f"{article.source.name}: "
                        f"{(article.title_ja or article.title_original)[:60]}"
                        "\n      -> "
                        f"{root.source.name}: "
                        f"{(root.title_ja or root.title_original)[:60]}"
                    )
                )

                article.duplicate_of = root

                if not dry_run:

                    article.save(
                        update_fields=[
                            "duplicate_of",
                        ]
                    )

            candidates.append(
                article
            )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Checked: {len(new_articles)}, "
                    f"Merged: {merged}"
                    + (" (dry run)" if dry_run else "")
                )
            )
        )
