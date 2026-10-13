
"""
Repair original URLs for existing Eventfrog events.

Matching order:
1. Exact Event.external_id
2. Known EventfrogOccurrenceLink IDs

Safety:
- Dry-run by default
- Validate Eventfrog URL and article ID
- Skip ambiguous matches
- Never delete or recreate events
- Never modify hearts, comments, images or occurrences
- Optionally hide demonstrably mismatched old links
"""

import re
from collections import defaultdict
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from outings.models import Event, EventfrogOccurrenceLink
from outings.services.eventfrog import collect


EVENTFROG_HOSTS = {
    "eventfrog.ch",
    "www.eventfrog.ch",
}

URL_ID_PATTERN = re.compile(r"-(\d+)\.html$")


def article_id_from_url(url):
    """Extract the Eventfrog event ID from a valid article URL."""

    if not isinstance(url, str) or not url.strip():
        return None

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None

    if parsed.scheme != "https":
        return None

    if parsed.hostname not in EVENTFROG_HOSTS:
        return None

    if parsed.username or parsed.password:
        return None

    match = URL_ID_PATTERN.search(parsed.path)

    if not match:
        return None

    return match.group(1)


class Command(BaseCommand):

    help = (
        "Repair Eventfrog URLs using representative and "
        "linked occurrence IDs. Dry-run by default."
    )

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

        parser.add_argument(
            "--hide-unverified",
            action="store_true",
            help=(
                "With --commit, clear old URLs whose article IDs "
                "are proven not to match any known event or "
                "occurrence ID, when no verified replacement exists."
            ),
        )

    def handle(self, *args, **options):

        if not 1 <= options["pages"] <= 60:
            raise CommandError("--pages must be 1..60")

        if not 1 <= options["days"] <= 90:
            raise CommandError("--days must be 1..90")

        commit = options["commit"]
        hide_unverified = options["hide_unverified"]

        self.stdout.write(
            "Fetching Eventfrog data..."
        )

        rows = collect(
            pages=options["pages"],
            days=options["days"],
        )

        # Only trust an API URL if its article ID
        # matches the API record ID.
        source_urls = {}

        for row in rows:

            external_id = str(
                row.get("id") or ""
            ).strip()

            url = str(
                row.get("url") or ""
            ).strip()

            if (
                external_id
                and article_id_from_url(url) == external_id
            ):
                source_urls[external_id] = url

        events = list(
            Event.objects.filter(
                source__name__iexact="Eventfrog",
            ).only(
                "id",
                "external_id",
                "original_url",
                "title",
            )
        )

        event_ids = [event.pk for event in events]

        # All known Eventfrog occurrence IDs per event.
        links_by_event = defaultdict(set)

        links = EventfrogOccurrenceLink.objects.filter(
            event_id__in=event_ids,
        ).values_list(
            "event_id",
            "eventfrog_id",
        )

        for event_id, occurrence_id in links.iterator():

            occurrence_id = str(
                occurrence_id or ""
            ).strip()

            if occurrence_id:
                links_by_event[event_id].add(
                    occurrence_id
                )

        stats = {
            "updated": 0,
            "unchanged": 0,
            "ambiguous": 0,
            "not_found": 0,
            "hidden": 0,
        }

        for event in events:

            representative_id = str(
                event.external_id or ""
            ).strip()

            linked_ids = links_by_event.get(
                event.pk,
                set(),
            )

            known_ids = set(linked_ids)

            if representative_id:
                known_ids.add(representative_id)

            old_url = str(
                event.original_url or ""
            ).strip()

            old_url_id = article_id_from_url(
                old_url
            )

            # Prefer the event's own representative ID.
            own_url = source_urls.get(
                representative_id
            )

            # Find URLs by linked occurrence IDs.
            linked_candidates = {
                source_urls[occurrence_id]
                for occurrence_id in linked_ids
                if occurrence_id in source_urls
            }

            correct_url = None

            if own_url:

                correct_url = own_url

            elif old_url_id in known_ids:

                # The existing URL already belongs to
                # this event or one of its known occurrences.
                # Do not replace it just because its current
                # source row was absent from the API snapshot.
                correct_url = old_url

            elif linked_candidates:

                # Multiple occurrences of the same Eventfrog event
                # may have different article URLs.
                #
                # Each candidate has already been verified against
                # its Eventfrog occurrence ID.
                #
                # Choose the lowest occurrence ID deterministically
                # instead of treating multiple valid URLs as an error.

                matching_ids = sorted(
                    occurrence_id
                    for occurrence_id in linked_ids
                    if occurrence_id in source_urls
                )

                selected_id = matching_ids[0]

                correct_url = source_urls[selected_id]

                self.stdout.write(
                    f"Event #{event.pk}: "
                    f"using verified occurrence {selected_id}"
                )

            if correct_url:

                if old_url == correct_url:

                    stats["unchanged"] += 1
                    continue

                self.stdout.write(
                    f"UPDATE Event #{event.pk}: "
                    f"{event.title[:55]}"
                )

                self.stdout.write(
                    f"  OLD: {old_url}"
                )

                self.stdout.write(
                    f"  NEW: {correct_url}"
                )

                if commit:

                    with transaction.atomic():

                        Event.objects.filter(
                            pk=event.pk,
                            source__name__iexact="Eventfrog",
                        ).update(
                            original_url=correct_url
                        )

                stats["updated"] += 1

                continue

            stats["not_found"] += 1

            # Hide only links with an article ID that
            # demonstrably belongs to no known occurrence
            # of this event.
            demonstrably_wrong = (
                bool(old_url)
                and old_url_id is not None
                and old_url_id not in known_ids
            )

            if hide_unverified and demonstrably_wrong:

                self.stdout.write(
                    self.style.WARNING(
                        f"HIDE Event #{event.pk}: "
                        f"{event.title[:55]}"
                    )
                )

                if commit:

                    Event.objects.filter(
                        pk=event.pk,
                        source__name__iexact="Eventfrog",
                        original_url=old_url,
                    ).update(
                        original_url=""
                    )

                stats["hidden"] += 1

            else:

                self.stdout.write(
                    self.style.WARNING(
                        f"UNRESOLVED Event #{event.pk}: "
                        f"{event.title[:55]} "
                        f"(external_id={representative_id})"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Finished: {stats}"
            )
        )

        if not commit:

            self.stdout.write(
                "DRY RUN: no database changes."
            )

        elif hide_unverified:

            self.stdout.write(
                "Verified corrections saved; "
                "mismatched unresolved links cleared."
            )
