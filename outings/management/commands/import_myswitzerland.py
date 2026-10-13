
"""
Import Switzerland Tourism data.

Default: dry run.
Use --commit to save changes.

Examples:

python manage.py import_myswitzerland --pages 1

python manage.py import_myswitzerland --pages 2 --commit
"""

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from outings.models import TouristSpot

from outings.services.myswitzerland import (
    SUPPORTED_TYPES,
    MySwitzerlandAPIError,
    fetch_spots,
    normalize_spot,
)


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
            "--commit",
            action="store_true",
        )

    def handle(self, *args, **options):

        spot_type = options["type"]
        pages = options["pages"]
        page_size = options["page_size"]
        commit = options["commit"]

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

            try:
                items = fetch_spots(
                    current_type,
                    pages=pages,
                    page_size=page_size,
                )
            except MySwitzerlandAPIError as exc:
                raise CommandError(
                    str(exc)
                ) from exc

            self.stdout.write(
                f"Fetched: {len(items)}"
            )

            for item in items:

                data = normalize_spot(
                    item,
                    current_type,
                )

                if data is None:
                    stats["skipped"] += 1
                    continue

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
                        )

                    continue

                changed_fields = []

                for field, value in data.items():

                    if getattr(
                        existing, field
                    ) != value:

                        changed_fields.append(
                            field
                        )

                if not changed_fields:

                    stats["unchanged"] += 1
                    continue

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

            self.stdout.write(
                f"Finished {current_type}"
            )

        self.stdout.write("")
        self.stdout.write(
            f"Summary: {stats}"
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
