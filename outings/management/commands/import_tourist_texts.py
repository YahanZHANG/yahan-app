"""Read hand-written introductions back from the export_tourist_texts CSV.

    python manage.py import_tourist_texts tourist_texts.csv          # check only
    python manage.py import_tourist_texts tourist_texts.csv --commit

Only rows with text in 「私の紹介文」 are used; an empty cell never clears
an introduction that is already there. Spots still waiting for AI text are
published once they get an introduction.
"""

import csv

from django.core.management.base import BaseCommand, CommandError

from outings.models import TouristSpot

TEXT_COLUMN = "私の紹介文"


def read_rows(path):
    # Excel may save as UTF-8 (with or without BOM) or as Shift_JIS.
    for encoding in ("utf-8-sig", "cp932"):
        try:
            with open(path, encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise CommandError("Could not read the file. Save it as CSV UTF-8.")


class Command(BaseCommand):
    help = "Import hand-written trip introductions from a CSV."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        rows = read_rows(options["path"])
        if rows and ("external_id" not in rows[0] or TEXT_COLUMN not in rows[0]):
            raise CommandError(f"The file needs the columns external_id and {TEXT_COLUMN}.")

        updated, unchanged, missing = 0, 0, []
        for row in rows:
            text = (row.get(TEXT_COLUMN) or "").strip()
            if not text:
                continue
            external_id = (row.get("external_id") or "").strip()
            spot = TouristSpot.objects.filter(external_id=external_id).first()
            if spot is None:
                missing.append(row.get("名前") or external_id)
                continue
            if spot.intro_ja == text:
                unchanged += 1
                continue
            updated += 1
            if options["commit"]:
                spot.intro_ja = text
                # A spot waiting for AI text is ready once it has a hand-written introduction.
                if spot.status == TouristSpot.Status.PENDING:
                    spot.status = TouristSpot.Status.PUBLISHED
                spot.save(update_fields=["intro_ja", "status", "updated_at"])

        verb = "Updated" if options["commit"] else "Would update"
        self.stdout.write(self.style.SUCCESS(f"{verb} {updated}; already the same {unchanged}."))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"{len(missing)} not in this database (import them first): " + ", ".join(missing[:20])
            ))
        if not options["commit"]:
            self.stdout.write("Nothing saved. Add --commit to save.")
