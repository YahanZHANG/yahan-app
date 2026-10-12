
import csv
import json
import re
import time

from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime, parse_date


AUDIT_DIR = Path("outings_audit")

FIELDS = [
    "source",
    "region",
    "candidate_url",
    "status",
    "title",
    "start_at",
    "end_at",
    "venue",
    "description",
    "date_in_html",
    "http_status",
    "reason",
]

DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|"
    r"\d{1,2}\.\d{1,2}\.\d{4})\b"
)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def same_site(a, b):
    host_a = (urlparse(a).hostname or "").removeprefix("www.")
    host_b = (urlparse(b).hostname or "").removeprefix("www.")
    return host_a == host_b


def event_type(types):
    if isinstance(types, str):
        types = [types]

    if not isinstance(types, list):
        return False

    for value in types:
        if not isinstance(value, str):
            continue

        name = value.rsplit("/", 1)[-1].split("#")[-1]

        if name.lower() == "event" or name.lower().endswith("event"):
            return True

    return False


def find_schema_events(soup):
    events = []

    def walk(obj):
        if isinstance(obj, list):
            for child in obj:
                walk(child)
            return

        if not isinstance(obj, dict):
            return

        if event_type(obj.get("@type", [])):
            events.append(obj)

        for value in obj.values():
            if isinstance(value, (list, dict)):
                walk(value)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(script.get_text()))
        except (ValueError, TypeError):
            continue

    return events


def get_location(value):
    if isinstance(value, list):
        value = value[0] if value else {}

    if isinstance(value, str):
        return clean(value)

    if not isinstance(value, dict):
        return ""

    return clean(value.get("name", ""))


def valid_iso_date(value):
    if not isinstance(value, str):
        return False

    value = value.strip()

    return bool(
        parse_datetime(value)
        or parse_date(value)
    )


def read_candidates(batch):
    batches = [1, 2] if batch == "all" else [int(batch)]
    items = []
    seen = set()

    for number in batches:
        path = AUDIT_DIR / (
            f"outings_candidates_batch{number:02d}.csv"
        )

        if not path.exists():
            raise CommandError(f"CSVが見つかりません: {path}")

        with path.open(
            newline="",
            encoding="utf-8-sig",
        ) as f:
            for row in csv.DictReader(f):
                url = row.get("event_url_candidate", "").strip()
                source = row.get("source", "").strip()

                if not url or not source:
                    continue

                parsed = urlparse(url)

                if parsed.scheme != "https":
                    continue

                key = (source, url.rstrip("/"))

                if key in seen:
                    continue

                seen.add(key)
                items.append(row)

    return items


class Command(BaseCommand):

    help = "Verify event candidate pages in batches; no DB writes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            choices=["1", "2", "all"],
            default="all",
        )

        parser.add_argument(
            "--limit-per-source",
            type=int,
            default=5,
        )

        parser.add_argument(
            "--delay",
            type=float,
            default=1.5,
        )

    def handle(self, *args, **options):
        batch = options["batch"]
        limit = options["limit_per_source"]
        delay = options["delay"]

        if not 1 <= limit <= 30:
            raise CommandError(
                "--limit-per-source は1〜30"
            )

        if delay < 1:
            raise CommandError("--delay は1秒以上")

        candidates = read_candidates(batch)

        grouped = defaultdict(list)

        for item in candidates:
            grouped[item["source"]].append(item)

        rows = []
        session = requests.Session()
        session.headers.update({
            "User-Agent": "YappOutingsResearch/0.1",
            "Accept": "text/html",
        })

        request_count = 0

        try:
            for source, items in grouped.items():
                self.stdout.write(f"\n=== {source} ===")

                # Prefer candidates that already have
                # nearby date evidence.
                rank = {
                    "DATE_AND_KEYWORD": 0,
                    "DATE_ONLY": 1,
                    "KEYWORD_ONLY": 2,
                }

                items.sort(
                    key=lambda r: rank.get(
                        r.get("confidence"), 3
                    )
                )

                for item in items[:limit]:
                    url = item["event_url_candidate"]

                    row = dict.fromkeys(FIELDS, "")

                    row.update({
                        "source": source,
                        "region": item.get("region", ""),
                        "candidate_url": url,
                        "status": "REVIEW",
                    })

                    try:
                        if request_count:
                            time.sleep(delay)

                        request_count += 1

                        response = session.get(
                            url,
                            timeout=20,
                            allow_redirects=True,
                        )

                        row["http_status"] = response.status_code
                        response.raise_for_status()

                        if not same_site(url, response.url):
                            row["reason"] = "別ドメインへ転送"
                            rows.append(row)
                            continue

                        if "html" not in response.headers.get(
                            "Content-Type", ""
                        ).lower():
                            row["status"] = "EXCLUDE"
                            row["reason"] = "HTMLではない"
                            rows.append(row)
                            continue

                        soup = BeautifulSoup(
                            response.text,
                            "html.parser",
                        )

                        heading = soup.find("h1")

                        row["title"] = (
                            clean(heading.get_text(" ", strip=True))
                            if heading else ""
                        )

                        main = soup.select_one("main") or soup.body

                        text = (
                            main.get_text(" ", strip=True)
                            if main else ""
                        )

                        matches = DATE_RE.findall(text)

                        row["date_in_html"] = (
                            " | ".join(matches[:5])
                        )

                        schema_events = find_schema_events(soup)

                        if schema_events:
                            event = schema_events[0]

                            row["title"] = clean(
                                event.get("name", "")
                            ) or row["title"]

                            row["start_at"] = clean(
                                event.get("startDate", "")
                            )
                            row["end_at"] = clean(
                                event.get("endDate", "")
                            )
                            row["venue"] = get_location(
                                event.get("location")
                            )
                            row["description"] = clean(
                                event.get("description", "")
                            )[:500]

                            if (
                                row["title"]
                                and valid_iso_date(row["start_at"])
                                and valid_iso_date(row["end_at"])
                                and row["venue"]
                            ):
                                row["status"] = "STRUCTURED"
                                row["reason"] = (
                                    "Schema.org Eventを検出。"
                                    "日時・会場の最終確認が必要"
                                )
                            else:
                                row["reason"] = (
                                    "構造化イベントに必須項目の不足"
                                )

                        elif row["title"] and (
                            matches or soup.find("time")
                        ):
                            row["reason"] = (
                                "日時の手がかりあり。"
                                "個別パーサーまたはHTML解析が必要"
                            )
                        else:
                            row["status"] = "EXCLUDE"
                            row["reason"] = (
                                "イベント詳細の証拠が不足"
                            )

                    except requests.RequestException as error:
                        row["status"] = "FETCH_ERROR"
                        row["reason"] = str(error)[:300]

                    except Exception as error:
                        row["status"] = "PARSE_ERROR"
                        row["reason"] = str(error)[:300]

                    rows.append(row)

                    self.stdout.write(
                        f"{row['status']}: "
                        f"{row['title'][:55] or url[:55]}"
                    )

        finally:
            session.close()

        AUDIT_DIR.mkdir(exist_ok=True)

        output = AUDIT_DIR / (
            f"outings_verified_batch{batch}.csv"
        )

        with output.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write("\n==========================")
        self.stdout.write(f"検証URL数: {len(rows)}")

        for status in (
            "STRUCTURED",
            "REVIEW",
            "EXCLUDE",
            "FETCH_ERROR",
            "PARSE_ERROR",
        ):
            count = sum(
                row["status"] == status
                for row in rows
            )

            self.stdout.write(f"{status}: {count}")

        self.stdout.write(f"\n結果CSV: {output}")
        self.stdout.write("DB変更なし。")
