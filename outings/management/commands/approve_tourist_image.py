
import json
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from outings.models import TouristSpot


DEFAULT_FILE = (
    Path("tourist_image_tests")
    / "commons_candidates.json"
)


def is_commons_url(url):
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "commons.wikimedia.org"
        )
    except (TypeError, ValueError):
        return False


def is_wikimedia_image(url):
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        return (
            parsed.scheme == "https"
            and (
                hostname == "upload.wikimedia.org"
                or hostname.endswith(".wikimedia.org")
            )
        )
    except (TypeError, ValueError):
        return False


class Command(BaseCommand):

    help = (
        "Approve one manually verified Wikimedia "
        "Commons image for a TouristSpot."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--spot-id",
            type=int,
            required=True,
        )

        parser.add_argument(
            "--candidate",
            type=int,
            required=True,
            help="Candidate number starting from 1.",
        )

        parser.add_argument(
            "--file",
            default=str(DEFAULT_FILE),
        )

        parser.add_argument(
            "--commit",
            action="store_true",
        )

    def handle(self, *args, **options):

        file_path = Path(options["file"])

        if not file_path.is_file():
            raise CommandError(
                f"Candidate JSON not found: {file_path}"
            )

        try:
            results = json.loads(
                file_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            raise CommandError(str(error)) from error

        spot_id = options["spot_id"]
        candidate_number = options["candidate"]

        matching = [
            item
            for item in results
            if item.get("spot_id") == spot_id
        ]

        if len(matching) != 1:
            raise CommandError(
                f"Spot {spot_id} is not uniquely found "
                "in the candidate file."
            )

        item = matching[0]
        candidates = item.get("candidates", [])

        if not 1 <= candidate_number <= len(candidates):
            raise CommandError(
                f"Candidate must be between 1 and "
                f"{len(candidates)}."
            )

        candidate = candidates[candidate_number - 1]

        required_fields = (
            "image_url",
            "source_url",
            "license",
            "license_url",
            "author",
            "file_title",
        )

        missing = [
            field
            for field in required_fields
            if not candidate.get(field)
        ]

        if missing:
            raise CommandError(
                "Missing attribution information: "
                + ", ".join(missing)
            )

        if not is_commons_url(
            candidate["source_url"]
        ):
            raise CommandError(
                "Source must be a Wikimedia Commons "
                "file page."
            )

        if not is_wikimedia_image(
            candidate["image_url"]
        ):
            raise CommandError(
                "Unexpected Wikimedia image URL."
            )

        if not candidate["license_url"].startswith(
            "https://"
        ):
            raise CommandError(
                "A valid HTTPS license URL is required."
            )

        spot = TouristSpot.objects.get(
            pk=spot_id,
        )

        if (
            spot.title_original
            != item.get("title")
        ):
            raise CommandError(
                "Spot title differs from the candidate "
                "report. Regenerate the report."
            )

        image_data = {
            "url": candidate["image_url"],
            "source_url": candidate["source_url"],
            "file_title": candidate["file_title"],
            "author": candidate["author"],
            "license": candidate["license"],
            "license_url": candidate["license_url"],
            "credit": (
                f'{candidate["author"]} / '
                f'{candidate["license"]}'
            ),
            "image_type": "wikimedia",
            "reviewed": True,
        }

        self.stdout.write("")
        self.stdout.write(
            f"Spot: {spot.title_original}"
        )
        self.stdout.write(
            f"Image: {image_data['file_title']}"
        )
        self.stdout.write(
            f"Author: {image_data['author']}"
        )
        self.stdout.write(
            f"License: {image_data['license']}"
        )
        self.stdout.write(
            f"Source: {image_data['source_url']}"
        )

        if not options["commit"]:

            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: Database was not changed."
                )
            )
            self.stdout.write(
                "Verify the location, authorship, "
                "license terms and any other rights."
            )
            self.stdout.write(
                "Add --commit to approve."
            )
            return

        with transaction.atomic():

            details = dict(spot.details or {})

            details["approved_image"] = image_data

            spot.details = details

            spot.save(
                update_fields=[
                    "details",
                    "updated_at",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Approved image saved successfully."
            )
        )
