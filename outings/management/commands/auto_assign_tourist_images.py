import math
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
    commons_candidates,
    search_commons,
)


# How far from a spot a geotagged photo may be taken (metres).
GEO_RADIUS = {
    TouristSpot.SpotType.DESTINATION: 3000,
    TouristSpot.SpotType.TOUR: 2000,
    TouristSpot.SpotType.ATTRACTION: 800,
    TouristSpot.SpotType.OFFER: 1500,
}

# File names that are rarely a good card photo. German words
# match inside compounds (Wanderkarte, Gemeindewappen).
NOT_A_PHOTO = re.compile(
    r"karte|wappen|grundriss|briefmarke|"
    r"\b(map|plan|logo|coat of arms|flag|fahne|sign|diagram|stamp|poster)\b"
)

MIN_WIDTH = 600


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
    title = normalize(candidate.get("file_title", ""))
    text = title + " " + normalize(candidate.get("description", ""))

    if len(name) < 3:
        return False

    # Short names (Zug, Bern, Chur) must appear as a
    # whole word in the file name itself.
    if len(name) < 5:
        return name in title.split()

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


def usable(candidate):
    return bool(
        candidate.get("author")
        and candidate.get("license")
        and candidate.get("license_url")
        and candidate.get("source_url")
        and candidate.get("width", 0) >= MIN_WIDTH
        and not NOT_A_PHOTO.search(
            normalize(candidate.get("file_title", ""))
        )
    )


def distance_m(lat1, lon1, lat2, lon2):
    rad = math.radians
    a = (
        math.sin(rad(lat2 - lat1) / 2) ** 2
        + math.cos(rad(lat1)) * math.cos(rad(lat2))
        * math.sin(rad(lon2 - lon1) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(math.sqrt(a))


def search_nearby(session, spot):
    """
    Geotagged Commons photos taken near the spot,
    closest first.
    """

    if spot.latitude is None or spot.longitude is None:
        return []

    response = session.get(
        COMMONS_API,
        params={
            "action": "query",
            "generator": "geosearch",
            "ggscoord": f"{spot.latitude}|{spot.longitude}",
            "ggsradius": GEO_RADIUS.get(spot.spot_type, 1500),
            "ggsnamespace": 6,
            "ggslimit": 30,
            "prop": "imageinfo|coordinates",
            "iiprop": "url|extmetadata|size|mime",
            "iiurlwidth": 800,
            "format": "json",
            "formatversion": 2,
        },
        timeout=30,
    )

    response.raise_for_status()

    pages = response.json().get("query", {}).get("pages", [])

    candidates = commons_candidates(pages, per_spot=30)

    def distance(candidate):
        point = candidate.get("coordinates") or {}
        if "lat" not in point or "lon" not in point:
            return math.inf
        return distance_m(
            spot.latitude, spot.longitude,
            point["lat"], point["lon"],
        )

    return sorted(candidates, key=distance)


def choose_photo(session, spot):
    """
    1. A photo whose name matches the spot.
    2. Otherwise the closest geotagged photo.

    Returns (candidate, method) or (None, "").
    """

    for candidate in search_commons(session, spot, per_spot=10):
        if usable(candidate) and relevant_photo(spot, candidate):
            return candidate, "name"

    for candidate in search_nearby(session, spot):
        if usable(candidate):
            return candidate, "nearby"

    return None, ""


class Command(BaseCommand):

    help = (
        "Automatically assign a Commons photo "
        "to tourism spots: by name, then by location."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
        )
        parser.add_argument(
            "--retry",
            action="store_true",
            help="Search again spots where no photo was found before.",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
        )

    def handle(self, *args, **options):

        limit = options["limit"]

        if not 1 <= limit <= 500:
            self.stderr.write(
                "--limit must be between 1 and 500"
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
        missing = []

        for spot in spots.iterator():

            details = dict(spot.details or {})

            # Never overwrite already approved images.
            if details.get("approved_image"):
                continue

            if details.get("commons_search_checked") and not options["retry"]:
                continue

            if searched >= limit:
                break

            searched += 1

            self.stdout.write(
                f"[{searched}/{limit}] "
                f"{spot.title_original}"
            )

            try:
                selected, method = choose_photo(session, spot)
            except requests.RequestException as error:
                self.stderr.write(
                    f"Search failed: {error}"
                )
                continue

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
                        "match": method,
                    }

                spot.details = details
                spot.save(
                    update_fields=[
                        "details",
                        "updated_at",
                    ]
                )

            if selected:
                assigned += 1
                label = "name" if method == "name" else "nearby"
                self.stdout.write(
                    f"  Selected ({label}): "
                    + selected["file_title"]
                )
            else:
                missing.append(spot)
                self.stdout.write(
                    "  No reliable candidate"
                )

            time.sleep(0.8)

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished: searched={searched}, "
                f"assigned={assigned}, "
                f"without photo={len(missing)}"
            )
        )

        for spot in missing:
            self.stdout.write(
                f"  No photo: [{spot.pk}] {spot.title_original}"
            )
