from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from news.models import Article

from news.services.combined_summary import (
    summarize_group,
)


class Command(BaseCommand):
    help = (
        "Write one summary that combines all reports "
        "for news covered by several sources."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--days",
            type=int,
            default=7,
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=30,
            help=(
                "Maximum number of AI calls."
            ),
        )


    def handle(
        self,
        *args,
        **options,
    ):

        since = (
            timezone.now()
            - timedelta(days=options["days"])
        )

        roots = (
            Article.objects
            .filter(
                duplicate_of__isnull=True,
                published_at__gte=since,
            )
            .filter(
                Q(duplicates__isnull=False)
                | ~Q(combined_from="")
            )
            .distinct()
            .select_related(
                "source",
            )
            .prefetch_related(
                "duplicates__source",
            )
            .order_by(
                "-published_at",
                "-id",
            )
        )

        updated = 0
        failed = 0

        for root in roots:

            # AI が使えないときに同じ失敗を繰り返さない
            if (
                updated >= options["limit"]
                or failed >= 5
            ):
                break

            try:

                changed = summarize_group(
                    root
                )

            except Exception as exc:

                failed += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"  ! {root.id}: {exc}"
                    )
                )

                continue

            if changed:

                updated += 1

                self.stdout.write(
                    f"  + {root.id} "
                    f"({len(root.source_articles)} sources): "
                    f"{(root.title_ja or root.title_original)[:60]}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Combined summaries updated: {updated}, "
                f"Failed: {failed}"
            )
        )
