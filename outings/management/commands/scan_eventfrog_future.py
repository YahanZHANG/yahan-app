
import csv
import os
import time

from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from outings.management.commands.export_eventfrog_candidates import (
    API_URL,
    CSV_FIELDS,
    transform_event,
)


TZ = ZoneInfo("Europe/Zurich")
OUT = Path("outings_audit")


class Command(BaseCommand):

    help = "Scan Eventfrog pages for genuinely upcoming events"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-pages",
            type=int,
            default=10,
        )
        parser.add_argument(
            "--per-page",
            type=int,
            default=100,
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
        )
        parser.add_argument(
            "--start-page",
            type=int,
            default=1,
        )

    def handle(self, *args, **options):

        token = os.environ.get(
            "EVENTFROG_API_TOKEN", ""
        ).strip()

        if not token:
            raise CommandError(
                "EVENTFROG_API_TOKEN が未設定です"
            )

        max_pages = options["max_pages"]
        start_page = options["start_page"]
        per_page = options["per_page"]
        days = options["days"]

        if start_page < 1:
            raise CommandError("--start-page は1以上")

        if not 1 <= max_pages <= 40:
            raise CommandError("--max-pages は1〜40")

        if not 1 <= per_page <= 1000:
            raise CommandError("--per-page は1〜1000")

        if not 1 <= days <= 90:
            raise CommandError("--days は1〜90")

        now = timezone.now().astimezone(TZ)
        horizon = now + timedelta(days=days)

        results = []
        page_report = []
        status_rows = []
        seen = set()

        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

        try:
            for page in range(start_page, start_page + max_pages):

                if page > 1:
                    time.sleep(2.5)

                params = {
                    "country": "CH",
                    "from": now.isoformat(),
                    "to": horizon.isoformat(),
                    "page": page,
                    "perPage": per_page,
                }

                try:
                    response = session.get(
                        API_URL,
                        params=params,
                        timeout=30,
                    )
                    response.raise_for_status()
                    payload = response.json()
                except (
                    requests.RequestException,
                    ValueError,
                ) as error:
                    raise CommandError(
                        f"Page {page}: API取得失敗: {error}"
                    ) from error

                if not isinstance(payload, dict):
                    raise CommandError(
                        "APIのJSON形式が想定外です"
                    )

                events = payload.get("events", [])

                if not isinstance(events, list):
                    raise CommandError(
                        "events がリストではありません"
                    )

                if not events:
                    break

                future_count = 0
                earliest = None
                latest = None

                for event in events:

                    if not isinstance(event, dict):
                        continue

                    event_id = str(event.get("id") or "")

                    if not event_id or event_id in seen:
                        continue

                    seen.add(event_id)

                    start = parse_datetime(
                        event.get("begin") or ""
                    )
                    end = parse_datetime(
                        event.get("end") or ""
                    )

                    if not start or not end:
                        continue

                    if timezone.is_naive(start):
                        continue

                    if timezone.is_naive(end):
                        continue

                    start = start.astimezone(TZ)
                    end = end.astimezone(TZ)

                    if earliest is None or start < earliest:
                        earliest = start

                    if latest is None or start > latest:
                        latest = start

                    if not (now <= start <= horizon):
                        continue

                    # =====================================================
                    # Eventfrog status audit
                    # Save source status before filtering public events.
                    # =====================================================

                    status_rows.append({
                        "eventfrog_id": event_id,
                        "begin": start.isoformat(),
                        "end": end.isoformat(),
                        "cancelled": str(event.get("cancelled")),
                        "published": str(event.get("published")),
                        "visible": str(event.get("visible")),
                        "checked_at": now.isoformat(),
                    })

                    # Existing publication filters remain unchanged.

                    if end <= start:
                        continue

                    if event.get("cancelled") is True:
                        continue

                    if end <= start:
                        continue

                    if event.get("cancelled") is True:
                        continue

                    if event.get("published") is not True:
                        continue

                    if event.get("visible") is not True:
                        continue

                    row = transform_event(event)

                    if not row["title"] or not row["url"]:
                        continue

                    results.append(row)
                    future_count += 1

                report = {
                    "page": page,
                    "received": len(events),
                    "future_events": future_count,
                    "earliest_begin": (
                        earliest.isoformat()
                        if earliest else ""
                    ),
                    "latest_begin": (
                        latest.isoformat()
                        if latest else ""
                    ),
                }

                page_report.append(report)

                self.stdout.write(
                    f"Page {page}: "
                    f"取得 {len(events)} / "
                    f"新規開催 {future_count} / "
                    f"累計 {len(results)}"
                )

                if len(events) < per_page:
                    break

        finally:
            session.close()

        OUT.mkdir(parents=True, exist_ok=True)

        results.sort(
            key=lambda x: (
                x["begin"],
                -x["score"],
                x["title"],
            )
        )

        suffix = f"p{start_page}_to_p{start_page + max_pages - 1}"

        future_file = OUT / f"eventfrog_future_events_{suffix}.csv"
        report_file = OUT / f"eventfrog_page_report_{suffix}.csv"

        status_file = OUT / f"eventfrog_status_{suffix}.csv"

        with status_file.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "eventfrog_id",
                    "begin",
                    "end",
                    "cancelled",
                    "published",
                    "visible",
                    "checked_at",
                ],
            )

            writer.writeheader()
            writer.writerows(status_rows)

        with future_file.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=CSV_FIELDS,
            )
            writer.writeheader()
            writer.writerows(results)

        with report_file.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "page",
                    "received",
                    "future_events",
                    "earliest_begin",
                    "latest_begin",
                ],
            )
            writer.writeheader()
            writer.writerows(page_report)

        self.stdout.write("\n========================")
        self.stdout.write(f"取得した異なるID: {len(seen)}")
        self.stdout.write(f"新規開催イベント: {len(results)}")
        self.stdout.write(f"イベントCSV: {future_file}")
        self.stdout.write(f"ページ診断CSV: {report_file}")
        self.stdout.write("DB変更なし")

        self.stdout.write(f"状態確認CSV: {status_file}")
        self.stdout.write(
            f"状態確認レコード: {len(status_rows)}"
        )

        cancelled_count = sum(
            row["cancelled"] == "True"
            for row in status_rows
        )

        self.stdout.write(
            f"明示的な中止イベント: {cancelled_count}"
        )
