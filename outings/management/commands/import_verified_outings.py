
import csv
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from outings.models import (
    Event,
    EventSource,
    EventLocation,
    EventOccurrence,
)


SOURCE_CONFIG = {
    "Stadt Winterthur": {
        "website_url": "https://stadt.winterthur.ch/veranstaltungen",
        "host": "stadt.winterthur.ch",
    },
    "Naturmuseum Winterthur": {
        "website_url": "https://natur.winterthur.ch/veranstaltungen",
        "host": "natur.winterthur.ch",
    },
}


def normalized_title(value):
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def parse_datetime(value):
    try:
        result = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
        if timezone.is_naive(result):
            return None
        return result
    except (ValueError, AttributeError):
        return None


class Command(BaseCommand):

    help = "Import verified Winterthur events as drafts"

    def add_arguments(self, parser):

        parser.add_argument(
            "--file",
            default="outings_audit/outings_verified_batchall.csv",
        )

        parser.add_argument(
            "--commit",
            action="store_true",
        )

    def handle(self, *args, **options):

        path = Path(options["file"])
        commit = options["commit"]

        if not path.is_file():
            raise CommandError(f"ファイルがありません: {path}")

        with path.open(
            encoding="utf-8-sig",
            newline="",
        ) as file:
            rows = list(csv.DictReader(file))

        # Museum first, then city calendar.
        # This lets the museum remain the primary source
        # for duplicate museum events.
        rows.sort(
            key=lambda row: (
                0 if row.get("source") == "Naturmuseum Winterthur"
                else 1,
                row.get("start_at", ""),
            )
        )

        counts = {
            "READY": 0,
            "CREATED": 0,
            "EXISTS": 0,
            "DUPLICATE": 0,
            "PAST": 0,
            "SKIP": 0,
        }

        seen = set()

        self.stdout.write(
            "モード: "
            + ("下書き保存" if commit else "プレビュー")
        )

        for row in rows:

            if row.get("status") != "STRUCTURED":
                continue

            source_name = row.get("source", "")
            config = SOURCE_CONFIG.get(source_name)

            if config is None:
                continue

            title = (row.get("title") or "").strip()
            venue = (row.get("venue") or "").strip()
            url = (row.get("candidate_url") or "").strip()

            start = parse_datetime(row.get("start_at") or "")
            end = parse_datetime(row.get("end_at") or "")

            if (
                not title
                or not venue
                or not url
                or not start
                or not end
                or end <= start
                or urlparse(url).scheme != "https"
                or urlparse(url).hostname != config["host"]
            ):
                counts["SKIP"] += 1
                continue

            if start <= timezone.now():
                counts["PAST"] += 1
                continue

            # Deduplicate across the two source calendars
            key = (
                normalized_title(title),
                start.astimezone(
                    timezone.get_default_timezone()
                ),
                normalized_title(venue),
            )

            if key in seen:
                counts["DUPLICATE"] += 1
                continue

            seen.add(key)

            external_id = urlparse(url).path.strip("/")

            source = EventSource.objects.filter(
                name=source_name
            ).first()

            if source:
                existing = Event.objects.filter(
                    source=source,
                    external_id=external_id,
                ).first()

                if existing:
                    counts["EXISTS"] += 1
                    continue

            # Check for duplicates across sources in the DB
            existing_occurrences = (
                EventOccurrence.objects.filter(
                    start_at=start,
                    event__location__city="Winterthur",
                )
                .select_related("event", "event__location")
            )

            duplicate_found = any(
                normalized_title(o.event.title) == key[0]
                and normalized_title(o.event.location.name) == key[2]
                for o in existing_occurrences
                if o.event.location is not None
            )

            if duplicate_found:
                counts["DUPLICATE"] += 1
                continue

            self.stdout.write(
                f"\n{title}\n"
                f"日時: {start} ～ {end}\n"
                f"会場: {venue}\n"
                f"情報源: {source_name}"
            )

            if not commit:
                counts["READY"] += 1
                continue

            with transaction.atomic():

                source, _ = EventSource.objects.get_or_create(
                    name=source_name,
                    defaults={
                        "website_url": config["website_url"],
                        "is_active": True,
                    },
                )

                location, _ = EventLocation.objects.get_or_create(
                    name=venue,
                    city="Winterthur",
                    canton="ZH",
                )

                event, created = Event.objects.get_or_create(
                    source=source,
                    external_id=external_id,
                    defaults={
                        "title": title,
                        "title_original": title,
                        "summary_ja": "",
                        "description_original": (
                            row.get("description") or ""
                        ),
                        "event_type": Event.EventType.ONE_TIME,
                        "status": Event.Status.DRAFT,
                        "location": location,
                        "original_url": url,
                        "is_free": False,
                        "price_text": "料金未確認・要確認",
                    },
                )

                if created:
                    EventOccurrence.objects.create(
                        event=event,
                        start_at=start,
                        end_at=end,
                    )
                    counts["CREATED"] += 1
                    self.stdout.write(f"CREATED: {event.pk}")
                else:
                    counts["EXISTS"] += 1

        self.stdout.write("\n====== 結果 ======")

        for key, count in counts.items():
            self.stdout.write(f"{key}: {count}")

        self.stdout.write(
            "完了。既存イベントは更新していません。"
        )
