
from django.core.management.base import BaseCommand

from outings.models import EventSource


# =========================================================
# Initial Outings Event Sources
# =========================================================

SOURCES = [
    {
        "name": "PBZ Zürich",
        "website_url": "https://www.pbz.ch/event-kalender/",
    },
    {
        "name": "GGG Stadtbibliothek Basel",
        "website_url": (
            "https://www.stadtbibliothekbasel.ch/"
            "de/veranstaltungen.html"
        ),
    },
    {
        "name": "Kanton Zug Veranstaltungen",
        "website_url": "https://veranstaltungen.zug.ch/events",
    },
]


# =========================================================
# Django Management Command
# =========================================================

class Command(BaseCommand):

    help = "Register initial Outings event sources"

    def handle(self, *args, **options):

        for item in SOURCES:

            source, created = EventSource.objects.update_or_create(
                name=item["name"],
                defaults={
                    "website_url": item["website_url"],
                },
            )

            action = "CREATE" if created else "UPDATE"

            self.stdout.write(
                f"{action}: {source.name}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Initial Outings sources registered."
            )
        )
