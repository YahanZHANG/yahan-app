
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError


OUT = Path("outings_audit")
TZ = ZoneInfo("Europe/Zurich")

FIELDS = [
    "review_status",
    "region",
    "city",
    "venue",
    "title",
    "first_begin",
    "occurrence_count",
    "occurrence_starts",
    "score",
    "priority",
    "matched_topics",
    "review_notes",
    "event_url",
    "description",
    "event_ids",
    "location_ids",
    "series_key",
]


def parse_date(value):
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).astimezone(TZ)
    except (ValueError, TypeError):
        return None


def preliminary_notes(row):
    notes = []

    title = (row.get("title") or "").casefold()
    topics = row.get("matched_topics") or ""

    if "日本関連" in topics:
        notes.append("日本関連判定を確認")

    if "fest" in title and "地域の祭り・市場" in topics:
        notes.append("祭り・市場の分類を確認")

    count = int(row.get("occurrence_count") or 0)

    if count > 1:
        notes.append(
            f"シリーズ{count}開催・日時要確認"
        )

    if not row.get("city") or not row.get("venue"):
        notes.append("会場・都市を確認")

    notes.append("料金・年齢・予約条件を確認")

    return " / ".join(notes)


class Command(BaseCommand):
    help = "Prepare Eventfrog review CSV without DB changes"

    def handle(self, *args, **options):

        input_path = OUT / "eventfrog_grouped_priority.csv"

        if not input_path.exists():
            raise CommandError(
                "eventfrog_grouped_priority.csv がありません"
            )

        with input_path.open(
            encoding="utf-8-sig",
            newline="",
        ) as f:
            source_rows = list(csv.DictReader(f))

        now = datetime.now(TZ)

        rows = []
        counts = Counter()

        for item in source_rows:

            start = parse_date(
                item.get("first_begin")
            )

            if not start:
                continue

            # Candidates in this snapshot already started
            # before now are not automatically rejected,
            # because they may represent ongoing events.
            review_status = (
                "NEW"
                if start >= now
                else "CHECK_ONGOING"
            )

            row = {
                field: item.get(field, "")
                for field in FIELDS
                if field not in (
                    "review_status",
                    "review_notes",
                )
            }

            row["review_status"] = review_status
            row["review_notes"] = preliminary_notes(item)

            rows.append(row)
            counts[item.get("region", "UNKNOWN")] += 1

        rows.sort(
            key=lambda r: (
                r["region"],
                -int(r["score"] or 0),
                r["first_begin"],
                r["title"],
            )
        )

        output_path = (
            OUT / "eventfrog_review_queue.csv"
        )

        with output_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=FIELDS,
            )
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(
            f"審査候補: {len(rows)}件"
        )

        for region, count in sorted(counts.items()):
            self.stdout.write(
                f"{region}: {count}件"
            )

        self.stdout.write(
            f"保存先: {output_path}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "完了。DB変更なし。"
            )
        )
