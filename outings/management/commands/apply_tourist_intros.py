"""Fill trip introductions from outings/data/tourist_intros.json.

The file maps the MySwitzerland title (title_original) to Taro's
hand-written Japanese introduction. Runs on every deploy (start.sh) and
after each trip import, so spots imported later still get their text.
An introduction already set (e.g. edited in admin) is kept unless
--overwrite. A spot waiting for AI text is published with it.

    python manage.py apply_tourist_intros            # fill empty ones
    python manage.py apply_tourist_intros --overwrite
"""

import json
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand

from outings.models import TouristSpot

DATA = Path(__file__).resolve().parents[2] / "data" / "tourist_intros.json"


def normalize(title):
    title = unicodedata.normalize("NFC", title or "")
    title = re.sub(r"[\"“”„«»]", "", title)
    title = title.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", title).strip().casefold()


def load_intros(path=None):
    path = path or DATA
    if not path.exists():
        return {}
    return {normalize(title): text.strip() for title, text in json.loads(path.read_text(encoding="utf-8")).items() if text.strip()}


class Command(BaseCommand):
    help = "Fill hand-written trip introductions from outings/data/tourist_intros.json."

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        intros = load_intros()
        if not intros:
            return
        filled = 0
        found = set()
        for spot in TouristSpot.objects.exclude(status=TouristSpot.Status.HIDDEN).only("pk", "title_original", "intro_ja", "status"):
            key = normalize(spot.title_original)
            text = intros.get(key)
            if not text:
                continue
            found.add(key)
            if spot.intro_ja == text or (spot.intro_ja and not options["overwrite"]):
                continue
            spot.intro_ja = text
            if spot.status == TouristSpot.Status.PENDING:
                spot.status = TouristSpot.Status.PUBLISHED
            spot.save(update_fields=["intro_ja", "status", "updated_at"])
            filled += 1
        self.stdout.write(f"Trip introductions: {filled} filled, {len(intros) - len(found)} not imported yet.")
