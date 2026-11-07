"""Fill 子連れスポット introductions from outings/data/family_intros.json.

The file maps FamilySpot.name to Taro's hand-written introduction. Runs on
every deploy (start.sh). An introduction already set (e.g. edited in admin)
is kept unless --overwrite.

    python manage.py apply_family_intros
    python manage.py apply_family_intros --overwrite
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from outings.models import FamilySpot

from .apply_tourist_intros import normalize

FAMILY_DATA = Path(__file__).resolve().parents[2] / "data" / "family_intros.json"


class Command(BaseCommand):
    help = "Fill hand-written 子連れスポット introductions from outings/data/family_intros.json."

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        if not FAMILY_DATA.exists():
            return
        intros = {normalize(name): text.strip() for name, text in json.loads(FAMILY_DATA.read_text(encoding="utf-8")).items() if text.strip()}
        filled, found = 0, set()
        for spot in FamilySpot.objects.only("pk", "name", "intro_ja"):
            key = normalize(spot.name)
            text = intros.get(key)
            if not text:
                continue
            found.add(key)
            if spot.intro_ja == text or (spot.intro_ja and not options["overwrite"]):
                continue
            spot.intro_ja = text
            spot.save(update_fields=["intro_ja", "updated_at"])
            filled += 1
        self.stdout.write(f"Family spot introductions: {filled} filled, {len(intros) - len(found)} without a spot.")
