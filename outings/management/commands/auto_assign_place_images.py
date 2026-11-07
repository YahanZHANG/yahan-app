"""
Wikimedia Commons photos for 子連れスポット and events that have no photo,
the same way trips get theirs: a photo whose file name matches the place,
otherwise the closest geotagged photo. Each place is searched once
(image_search_done); --retry searches again. Never replaces a photo
that is already set.
"""

import os
import time
from types import SimpleNamespace

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from outings import sunny
from outings.models import Event, FamilySpot

from .auto_assign_tourist_images import (
    relevant_photo,
    search_nearby,
    usable,
)
from .find_tourist_images import USER_AGENT, search_commons

FAMILY_RADIUS = 800   # metres around a 子連れスポット
VENUE_RADIUS = 400    # metres around an event venue
TOWN_RADIUS = 2000    # metres around the town when the venue has no coordinates


def make_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": os.environ.get("WIKIMEDIA_USER_AGENT", USER_AGENT),
        "Accept": "application/json",
    })
    return session


def pick(session, name, lat, lon, radius):
    """(candidate, 'name'|'nearby') or (None, '')."""
    place = SimpleNamespace(title_original=name or "", latitude=lat, longitude=lon, spot_type=None)
    if place.title_original.strip():
        for candidate in search_commons(session, place, per_spot=10):
            if usable(candidate) and relevant_photo(place, candidate):
                return candidate, "name"
    if lat is not None and lon is not None:
        for candidate in search_nearby(session, place, radius=radius):
            if usable(candidate):
                return candidate, "nearby"
    return None, ""


def credit(candidate):
    return f"{candidate['author']} / {candidate['license']}（Wikimedia Commons）"[:300]


def family_photo(session, spot):
    if spot.latitude is None or spot.longitude is None:
        sunny.locate(spot)
    return pick(session, spot.name, spot.latitude, spot.longitude, FAMILY_RADIUS)


def event_photo(session, event):
    loc = event.location
    if loc is None:
        return None, ""
    lat = float(loc.latitude) if loc.latitude is not None else None
    lon = float(loc.longitude) if loc.longitude is not None else None
    # The venue itself, then the town around it.
    found, method = pick(session, loc.name, lat, lon, VENUE_RADIUS if lat is not None else None)
    if found:
        return found, method
    return pick(session, loc.city, lat, lon, TOWN_RADIUS) if loc.city else (None, "")


class Command(BaseCommand):
    help = "Automatically add Wikimedia photos to 子連れスポット and events without a photo."

    def add_arguments(self, parser):
        parser.add_argument("--target", choices=["family", "events", "all"], default="all")
        parser.add_argument("--limit", type=int, default=40, help="Max places searched per target")
        parser.add_argument("--retry", action="store_true", help="Search again places where nothing was found")
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--pause", type=float, default=0.8)

    def handle(self, *args, **opts):
        if not 1 <= opts["limit"] <= 500:
            self.stderr.write("--limit must be between 1 and 500")
            return
        session = make_session()
        results = []
        if opts["target"] in ("family", "all"):
            spots = FamilySpot.objects.filter(image_url="", image_removed=False)
            if not opts["retry"]:
                spots = spots.filter(image_search_done=False)
            results.append(self.run("子連れスポット", spots.order_by("sort_order", "pk"), family_photo, session, opts))
        if opts["target"] in ("events", "all"):
            now = timezone.now()
            upcoming = Q(occurrences__end_at__gt=now) | Q(occurrences__end_at__isnull=True, occurrences__start_at__gt=now)
            events = Event.objects.filter(
                upcoming, image_url="", image_removed=False, status=Event.Status.PUBLISHED,
            ).distinct().select_related("location")
            if not opts["retry"]:
                events = events.filter(image_search_done=False)
            results.append(self.run("イベント", events.order_by("pk"), event_photo, session, opts))
        return "; ".join(results)

    def run(self, label, items, finder, session, opts):
        searched = assigned = 0
        for item in items[: opts["limit"]]:
            searched += 1
            try:
                found, method = finder(session, item)
            except requests.RequestException as error:
                self.stderr.write(f"  {item}: search failed: {error}")
                continue
            if found:
                assigned += 1
                self.stdout.write(f"  {item}: {found['file_title']} ({method})")
            else:
                self.stdout.write(f"  {item}: no photo")
            if opts["commit"]:
                fields = ["image_search_done"]
                item.image_search_done = True
                if found:
                    item.image_url = found["image_url"]
                    item.image_credit = credit(found)
                    fields += ["image_url", "image_credit"]
                item.save(update_fields=fields)
            if opts["pause"]:
                time.sleep(opts["pause"])
        summary = f"{label}: searched={searched}, assigned={assigned}"
        self.stdout.write(self.style.SUCCESS(summary))
        return summary
