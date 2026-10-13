
"""
Repair original URLs of existing Eventfrog events.

Dry-run by default.
Only matches an event using its exact external_id.
Does not recreate events or modify hearts/comments.
"""

from urllib.parse import urlparse
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from outings.models import Event
from outings.services.eventfrog import collect


def valid_eventfrog_url(url, external_id):
    if not isinstance(url, str):
        return False

    parsed = urlparse(url.strip())

    if parsed.scheme != "https":
        return False

    if parsed.hostname not in (
        "eventfrog.ch",
        "www.eventfrog.ch",
    ):
        return False

    if parsed.username or parsed.password:
        return False

    # Eventfrog article URLs end with the event ID.
    match = re.search(
        r"-(\d+)\.html$",
        parsed.path,
    )

    return bool(
        match
        and match.group(1) == str(external_id)
    )


class Command(BaseCommand):

    help = "Repair existing Eventfrog source URLs."

    def add_arguments(self, parser):

        parser.add_argument(
            "--commit",
            action="store_true",
        )

        parser.add_argument(
            "--pages",
            type=int,
            default=30,
        )

        parser.add_argument(
            "--days",
            type=int,
            default=45,
        )

    def handle(self, *args, **options):

        rows = collect(
            pages=options["pages"],
            days=options["days"],
        )

        source_urls = {}

        for row in rows:

            external_id = str(
                row.get("id") or ""
            ).strip()

            url = str(
                row.get("url") or ""
            ).strip()

            if valid_eventfrog_url(
                url,
                external_id,
            ):
                source_urls[external_id] = url

        events = Event.objects.filter(
            source__name__iexact="Eventfrog",
        )

        updated = 0
        unchanged = 0
        missing = 0

        for event in events.iterator():

            external_id = str(
                event.external_id or ""
            ).strip()

            correct_url = source_urls.get(
                external_id
            )

            if not correct_url:
                missing += 1
                continue

            if event.original_url == correct_url:
                unchanged += 1
                continue

            self.stdout.write(
                f"Event #{event.pk}: "
                f"{event.original_url} "
                f"-> {correct_url}"
            )

            if options["commit"]:

                with transaction.atomic():

                    Event.objects.filter(
                        pk=event.pk,
                        source__name__iexact="Eventfrog",
                        external_id=external_id,
                    ).update(
                        original_url=correct_url
                    )

            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Complete: "
                f"correctable={updated}, "
                f"unchanged={unchanged}, "
                f"not_found={missing}, "
                f"commit={options['commit']}"
            )
        )
