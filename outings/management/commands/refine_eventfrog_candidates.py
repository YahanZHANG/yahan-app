
import csv
import json
import re

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError


DIR = Path("outings_audit")
TZ = ZoneInfo("Europe/Zurich")

FIELDS = [
    "priority",
    "score",
    "title",
    "begin",
    "end",
    "id",
    "group_id",
    "series_count",
    "location_ids",
    "organizer",
    "url",
    "matched_topics",
]


def parse_date(value):
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).astimezone(TZ)
    except (ValueError, AttributeError):
        return None


def normalize(value):
    return re.sub(
        r"\s+", " ", str(value or "")
    ).strip().casefold()


def write_csv(path, rows):
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)


class Command(BaseCommand):
    help = "Refine Eventfrog candidates without DB changes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
        )

    def handle(self, *args, **options):
        raw_path = DIR / "eventfrog_raw.json"
        csv_path = DIR / "eventfrog_candidates_all.csv"

        if not raw_path.exists() or not csv_path.exists():
            raise CommandError(
                "先にEventfrogの500件取得を実行してください"
            )

        with raw_path.open(encoding="utf-8") as f:
            raw = json.load(f)

        with csv_path.open(
            encoding="utf-8-sig",
            newline="",
        ) as f:
            candidates = list(csv.DictReader(f))

        by_id = {
            str(item.get("id")): item
            for item in raw
        }

        now = datetime.now(TZ)
        horizon = now + timedelta(days=options["days"])

        groups = defaultdict(list)

        for row in candidates:
            original = by_id.get(row["id"], {})

            start = parse_date(row["begin"])
            end = parse_date(row["end"])

            if not start or not end or end <= now:
                continue

            if start > horizon:
                continue

            if row.get("priority") == "LOW":
                continue

            location_ids = original.get("locationIds") or []

            # Same title at the same location is treated
            # as a provisional series, not necessarily
            # as an exact duplicate.
            key = (
                normalize(row["title"]),
                tuple(sorted(map(str, location_ids))),
            )

            enriched = {
                **row,
                "_start": start,
                "_end": end,
            }

            groups[key].append(enriched)

        upcoming = []
        ongoing = []

        for items in groups.values():
            items.sort(key=lambda r: r["_start"])

            future_items = [
                r for r in items
                if r["_start"] >= now
            ]

            # Prefer the next future occurrence.
            representative = (
                future_items[0]
                if future_items
                else max(
                    items,
                    key=lambda r: r["_end"]
                )
            )

            output = {
                key: representative.get(key, "")
                for key in FIELDS
                if key != "series_count"
            }

            output["series_count"] = len(items)

            if future_items:
                upcoming.append(output)
            else:
                ongoing.append(output)

        def sort_key(row):
            return (
                -int(row["score"]),
                row["begin"],
            )

        upcoming.sort(key=sort_key)
        ongoing.sort(key=sort_key)

        upcoming_file = DIR / "eventfrog_upcoming_refined.csv"
        ongoing_file = DIR / "eventfrog_ongoing_refined.csv"

        write_csv(upcoming_file, upcoming)
        write_csv(ongoing_file, ongoing)

        self.stdout.write("\n========================")
        self.stdout.write(
            f"元データ: {len(candidates)}件"
        )
        self.stdout.write(
            f"新規開催候補（グループ単位）: {len(upcoming)}件"
        )
        self.stdout.write(
            f"継続開催候補（グループ単位）: {len(ongoing)}件"
        )
        self.stdout.write(f"新規: {upcoming_file}")
        self.stdout.write(f"継続: {ongoing_file}")
        self.stdout.write("DB変更なし")
