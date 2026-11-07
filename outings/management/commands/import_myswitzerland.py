"""
Import Switzerland Tourism data.

Default: dry run (the API is read, the database is not changed).
Use --commit to save changes.

New records are saved as 確認待ち (pending): they stay hidden until
enrich_tourist_spots has written the Japanese title and summary, which
then publishes them. Records already in the DB keep their status, so
spots hidden in admin stay hidden.

Examples:

python manage.py import_myswitzerland --pages 1

python manage.py import_myswitzerland --all            # count everything
python manage.py import_myswitzerland --all --commit   # save everything
"""

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from outings.models import TouristSpot

from outings.services.myswitzerland import (
    SUPPORTED_TYPES,
    MySwitzerlandAPIError,
    iter_spot_pages,
    normalize_spot,
)


# Rough AI cost of one spot in enrich_tourist_spots (translation +
# scoring) with gpt-4.1-mini, used only for the estimate printed at
# the end. enrich_tourist_spots prints the real cost from the API usage.
ESTIMATED_USD_PER_SPOT = 0.0012


class Command(BaseCommand):

    help = "Import Switzerland Tourism data"

    def add_arguments(self, parser):

        parser.add_argument(
            "--type",
            choices=SUPPORTED_TYPES + ("all",),
            default="all",
        )

        parser.add_argument(
            "--pages",
            type=int,
            default=1,
        )

        parser.add_argument(
            "--page-size",
            type=int,
            default=10,
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Every page (same as --pages 1000 --page-size 100)",
        )

        parser.add_argument(
            "--commit",
            action="store_true",
        )

    def handle(self, *args, **options):

        spot_type = options["type"]
        pages = options["pages"]
        page_size = options["page_size"]
        commit = options["commit"]

        if options["all"]:
            pages = 1000
            page_size = 100

        if not 1 <= pages <= 1000:
            raise CommandError(
                "--pages must be between 1 and 1000"
            )

        if not 1 <= page_size <= 100:
            raise CommandError(
                "--page-size must be between 1 and 100"
            )

        types = (
            SUPPORTED_TYPES
            if spot_type == "all"
            else (spot_type,)
        )

        stats = {
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped": 0,
        }

        for current_type in types:

            self.stdout.write("")
            self.stdout.write(
                f"Fetching {current_type}..."
            )

            fetched = 0

            try:
                for items in iter_spot_pages(
                    current_type,
                    pages=pages,
                    page_size=page_size,
                ):
                    fetched += len(items)
                    with transaction.atomic():
                        for item in items:
                            self.save_item(
                                item,
                                current_type,
                                stats,
                                commit,
                            )
            except MySwitzerlandAPIError as exc:
                raise CommandError(
                    f"{exc} (pages already read were "
                    f"{'saved' if commit else 'counted'}; "
                    "a rerun skips unchanged records)"
                ) from exc

            self.stdout.write(
                f"Finished {current_type}: fetched {fetched}"
            )

        self.stdout.write("")
        self.stdout.write(
            f"Summary: {stats}"
        )

        waiting = (
            TouristSpot.objects.filter(
                status=TouristSpot.Status.PENDING,
                ai_reviewed_at__isnull=True,
            ).count()
        )

        if not commit:
            waiting += stats["created"]

        self.stdout.write(
            f"Waiting for Japanese text: {waiting} "
            f"(AI about ${waiting * ESTIMATED_USD_PER_SPOT:.2f})"
        )

        if commit:
            self.stdout.write(
                self.style.SUCCESS(
                    "Database changes saved."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no database changes."
                )
            )

    def save_item(self, item, current_type, stats, commit):

        data = normalize_spot(
            item,
            current_type,
        )

        if data is None:
            stats["skipped"] += 1
            return

        external_id = data.pop(
            "external_id"
        )

        normalized_type = data.pop(
            "spot_type"
        )

        lookup = {
            "source_name": (
                "Switzerland Tourism"
            ),
            "spot_type": normalized_type,
            "external_id": external_id,
        }

        existing = (
            TouristSpot.objects.filter(
                **lookup
            ).first()
        )

        if existing is None:

            stats["created"] += 1

            if commit:
                TouristSpot.objects.create(
                    **lookup,
                    **data,
                    status=TouristSpot.Status.PENDING,
                )

            return

        changed_fields = [
            field
            for field, value in data.items()
            if getattr(existing, field) != value
        ]

        if not changed_fields:
            stats["unchanged"] += 1
            return

        stats["updated"] += 1

        if commit:

            for field in changed_fields:
                setattr(
                    existing,
                    field,
                    data[field],
                )

            existing.save(
                update_fields=(
                    changed_fields
                    + ["updated_at"]
                )
            )
