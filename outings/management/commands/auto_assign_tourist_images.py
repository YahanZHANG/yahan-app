
import os
import re
import time
import unicodedata

import requests

from django.core.management.base import BaseCommand

from outings.models import TouristSpot

from .find_tourist_images import (
    COMMONS_API,
    USER_AGENT,
    search_commons,
)


def normalize(value):
    value = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )
    return re.sub(
        r"[^a-z0-9]+", " ",
        value.lower(),
    ).strip()


def relevant_photo(spot, candidate):
    """
    Check whether the image title or description
    refers to the specific destination.

    This is a conservative basic filter,
    not a guarantee of geographical accuracy.
    """
    name = normalize(spot.title_original)
    text = normalize(
        candidate.get("file_title", "")
        + " "
        + candidate.get("description", "")
    )

    # Ignore very short / ambiguous place names.
    if len(name) < 5:
        return False

    if name in text:
        return True

    # For long titles, require meaningful keywords.
    words = [
        word for word in name.split()
        if len(word) >= 5
    ]

    if not words:
        return False

    matches = sum(
        1 for word in words if word in text.split()
    )

    return matches >= min(2, len(words))


class Command(BaseCommand):

    help = (
        "Automatically assign the first relevant "
        "Commons photo to tourism spots."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
        )
        parser.add_argument(
            "--commit",
            action="store_true",
        )

    def handle(self, *args, **options):

        limit = options["limit"]

        if not 1 <= limit <= 100:
            self.stderr.write(
                "--limit must be between 1 and 100"
            )
            return

        spots = TouristSpot.objects.filter(
            status=TouristSpot.Status.PUBLISHED,
        ).order_by("-ai_quality_score", "pk")

        session = requests.Session()
        session.headers.update({
            "User-Agent": os.environ.get(
                "WIKIMEDIA_USER_AGENT",
                USER_AGENT,
            ),
            "Accept": "application/json",
        })

        assigned = 0
        searched = 0

        for spot in spots.iterator():

            details = dict(spot.details or {})

            # Never overwrite already approved images.
            if details.get("approved_image"):
                continue

            # Skip previous unsuccessful searches
            # unless a future retry policy is added.
            if details.get("commons_search_checked"):
                continue

            if searched >= limit:
                break

            searched += 1

            self.stdout.write(
                f"[{searched}/{limit}] "
                f"{spot.title_original}"
            )

            try:
                candidates = search_commons(
                    session,
                    spot,
                    per_spot=5,
                )
            except requests.RequestException as error:
                self.stderr.write(
                    f"Search failed: {error}"
                )
                continue

            selected = next(
                (
                    candidate
                    for candidate in candidates
                    if relevant_photo(spot, candidate)
                    and candidate.get("author")
                    and candidate.get("license")
                    and candidate.get("license_url")
                    and candidate.get("source_url")
                ),
                None,
            )

            if options["commit"]:

                details["commons_search_checked"] = True

                if selected:
                    details["approved_image"] = {
                        "url": selected["image_url"],
                        "source_url": selected["source_url"],
                        "file_title": selected["file_title"],
                        "author": selected["author"],
                        "license": selected["license"],
                        "license_url": selected["license_url"],
                        "credit": (
                            selected["author"]
                            + " / "
                            + selected["license"]
                        ),
                        "image_type": "wikimedia",
                        "reviewed": False,
                        "selection_method": "automatic",
                    }

                    assigned += 1

                spot.details = details
                spot.save(
                    update_fields=[
                        "details",
                        "updated_at",
                    ]
                )

            if selected:
                self.stdout.write(
                    "  Selected: "
                    + selected["file_title"]
                )
            else:
                self.stdout.write(
                    "  No reliable candidate"
                )

            time.sleep(0.8)

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished: searched={searched}, "
                f"assigned={assigned}"
            )
        )
