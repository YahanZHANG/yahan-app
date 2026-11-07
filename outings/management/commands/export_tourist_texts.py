"""Write the trips to a CSV (opens in Excel) for writing introductions by hand.

    python manage.py export_tourist_texts tourist_texts.csv

Fill the 「私の紹介文」 column and read it back with import_tourist_texts.
Rows are matched on external_id, so the file works on any copy of the
database, production included.
"""

import csv

from django.core.management.base import BaseCommand

from outings.models import TouristSpot

COLUMNS = ["external_id", "種類", "名前", "日本語のタイトル", "いまの紹介文（AI）", "私の紹介文"]


class Command(BaseCommand):
    help = "Export trips to a CSV for hand-written introductions."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--all", action="store_true", help="Include hidden and waiting spots too.")

    def handle(self, *args, **options):
        spots = TouristSpot.objects.order_by("spot_type", "title_original")
        if not options["all"]:
            spots = spots.filter(status=TouristSpot.Status.PUBLISHED)
        # utf-8-sig so Excel shows Japanese correctly.
        with open(options["path"], "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            for spot in spots:
                writer.writerow([
                    spot.external_id,
                    spot.get_spot_type_display(),
                    spot.title_original,
                    spot.title_ja,
                    spot.summary_ja,
                    spot.intro_ja,
                ])
        self.stdout.write(self.style.SUCCESS(f"{spots.count()} spots written to {options['path']}"))
