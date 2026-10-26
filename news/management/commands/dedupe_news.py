from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.services.deduplicator import (
    WINDOW,
    Similarity,
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
                "Use only word similarity "
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

        recent = list(recent)

        # まだ重複チェックしていない記事
        new_articles = [
            article
            for article in recent
            if article.dedupe_checked_at is None
            and article.published_at >= since
        ]

        candidates = [
            article
            for article in recent
            if article.dedupe_checked_at is not None
        ]

        if not new_articles:

            self.stdout.write(
                self.style.SUCCESS(
                    "No new articles to check."
                )
            )

            return

        # 言葉の重みは、比べる記事全体から作る
        similarity = Similarity(
            recent
        )

        now = timezone.now()

        merged = 0
        failed = 0

        for article in new_articles:

            try:

                root, score = find_duplicate_root(
                    article,
                    candidates,
                    similarity,
                    use_ai=not options["no_ai"],
                )

            except Exception as exc:

                # AI が使えないときは次回の更新でもう一度確認する
                failed += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"  ! check failed: {exc}"
                    )
                )

                continue

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

            article.dedupe_checked_at = now

            if not dry_run:

                article.save(
                    update_fields=[
                        "duplicate_of",
                        "dedupe_checked_at",
                    ]
                )

            candidates.append(
                article
            )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Checked: {len(new_articles)}, "
                    f"Merged: {merged}, "
                    f"Failed: {failed}"
                    + (" (dry run)" if dry_run else "")
                )
            )
        )
