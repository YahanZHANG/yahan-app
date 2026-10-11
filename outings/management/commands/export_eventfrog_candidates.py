
import csv
import json
import os
import re
import time

from collections import Counter
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


API_URL = "https://api.eventfrog.net/public/v1/events"
SWISS_TZ = ZoneInfo("Europe/Zurich")

OUTPUT_DIR = Path("outings_audit")

CSV_FIELDS = [
    "priority",
    "score",
    "matched_topics",
    "id",
    "group_id",
    "title",
    "begin",
    "end",
    "organizer",
    "location_ids",
    "location_alias",
    "rubric_id",
    "description",
    "url",
    "website_url",
    "cancelled",
    "sold_out",
    "published",
    "visible",
]


# =========================================================
# Relevance rules: initial heuristic only
# =========================================================

TOPICS = {
    "日本関連": (
        10,
        [
            r"japan",
            r"japanisch",
            r"japanese",
            r"日本",
            r"和食",
            r"anime",
            r"manga",
            r"origami",
            r"kimono",
            r"bonsai",
            r"shodo",
            r"bonsai",
        ],
    ),
    "子ども・家族": (
        8,
        [
            r"kinder",
            r"familien",
            r"family",
            r"children",
            r"kids",
            r"baby",
            r"kleinkind",
            r"eltern",
            r"märchen",
            r"maerchen",
            r"kindertheater",
        ],
    ),
    "美術館・博物館": (
        6,
        [
            r"museum",
            r"kunsthaus",
            r"kunstmuseum",
            r"naturmuseum",
            r"ausstellung",
            r"exhibition",
            r"vernissage",
        ],
    ),
    "図書館・読書": (
        6,
        [
            r"bibliothek",
            r"library",
            r"lesung",
            r"vorlesen",
            r"bilderbuch",
            r"storytelling",
            r"shared reading",
        ],
    ),
    "体験・ワークショップ": (
        5,
        [
            r"workshop",
            r"atelier",
            r"basteln",
            r"mitmachen",
            r"töpfern",
            r"toepfern",
            r"zeichnen",
            r"experiment",
            r"hands.on",
        ],
    ),
    "地域の祭り・市場": (
        4,
        [
            r"festival",
            r"fest",
            r"markt",
            r"märit",
            r"maerit",
            r"street food",
            r"flohmarkt",
            r"weihnachtsmarkt",
        ],
    ),
    "語学・交流": (
        4,
        [
            r"sprachcafé",
            r"sprachcafe",
            r"english café",
            r"english cafe",
            r"deutsch lernen",
            r"language exchange",
            r"conversation",
            r"treffpunkt",
        ],
    ),
}


def localized_text(value):
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for language in ("de", "en", "fr", "it", "ja"):
            result = value.get(language)
            if isinstance(result, str) and result.strip():
                return result.strip()

        for result in value.values():
            if isinstance(result, str) and result.strip():
                return result.strip()

    return ""


def strip_html(value):
    return BeautifulSoup(
        value or "",
        "html.parser",
    ).get_text(" ", strip=True)


def normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def score_event(title, description):
    # Use full titles, but only a short excerpt of descriptions
    # to avoid promoting unrelated keyword-heavy pages.
    text = (title + " " + description[:600]).casefold()

    score = 0
    matches = []

    for topic, (points, patterns) in TOPICS.items():
        if any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in patterns
        ):
            score += points
            matches.append(topic)

    if score >= 10:
        priority = "HIGH"
    elif score >= 5:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return priority, score, " / ".join(matches)


def transform_event(event):
    title = normalize_space(
        localized_text(event.get("title"))
    )

    short_description = localized_text(
        event.get("shortDescription")
    )

    html_description = localized_text(
        event.get("descriptionAsHTML")
    )

    description = normalize_space(
        strip_html(html_description)
        or short_description
    )

    priority, score, matched = score_event(
        title,
        description,
    )

    location_ids = event.get("locationIds") or []

    return {
        "priority": priority,
        "score": score,
        "matched_topics": matched,
        "id": str(event.get("id") or ""),
        "group_id": str(event.get("groupId") or ""),
        "title": title,
        "begin": event.get("begin") or "",
        "end": event.get("end") or "",
        "organizer": event.get("organizerName") or "",
        "location_ids": json.dumps(
            location_ids,
            ensure_ascii=False,
        ),
        "location_alias": localized_text(
            event.get("locationAlias")
        ),
        "rubric_id": event.get("rubricId") or "",
        "description": description[:1200],
        "url": event.get("url") or "",
        "website_url": event.get("websiteUrl") or "",
        "cancelled": event.get("cancelled", False),
        "sold_out": event.get("soldOut", False),
        "published": event.get("published", False),
        "visible": event.get("visible", False),
    }


class Command(BaseCommand):

    help = "Export and rank Eventfrog events without DB writes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
        )

        parser.add_argument(
            "--days",
            type=int,
            default=30,
        )

        parser.add_argument(
            "--per-page",
            type=int,
            default=100,
        )


    def handle(self, *args, **options):

        token = os.environ.get(
            "EVENTFROG_API_TOKEN", ""
        ).strip()

        if not token:
            raise CommandError(
                "EVENTFROG_API_TOKEN が未設定です。"
            )

        limit = options["limit"]
        days = options["days"]
        per_page = options["per_page"]

        if not 1 <= limit <= 5000:
            raise CommandError("--limit は1〜5000")

        if not 1 <= days <= 90:
            raise CommandError("--days は1〜90")

        if not 1 <= per_page <= 1000:
            raise CommandError("--per-page は1〜1000")

        start = timezone.now().astimezone(SWISS_TZ)
        end = start + timedelta(days=days)

        events = []
        seen = set()
        page = 1

        session = requests.Session()

        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

        try:
            while len(events) < limit:

                remaining = limit - len(events)
                page_size = min(
                    remaining,
                    per_page,
                )

                params = {
                    "country": "CH",
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "page": page,
                    "perPage": page_size,
                }

                self.stdout.write(
                    f"Page {page}: "
                    f"最大{page_size}件を取得"
                )

                try:
                    response = session.get(
                        API_URL,
                        params=params,
                        timeout=30,
                    )

                    if response.status_code in (401, 403):
                        raise CommandError(
                            f"API認証エラー: HTTP "
                            f"{response.status_code}"
                        )

                    response.raise_for_status()
                    payload = response.json()

                except requests.RequestException as error:
                    raise CommandError(
                        f"API通信エラー: {type(error).__name__}: {error}"
                    ) from error

                except ValueError as error:
                    raise CommandError(
                        "API応答がJSONではありません"
                    ) from error

                if not isinstance(payload, dict):
                    raise CommandError("想定外のAPI応答")

                batch = payload.get("events", [])

                if not isinstance(batch, list):
                    raise CommandError(
                        "eventsがリストではありません"
                    )

                if not batch:
                    break

                new_count = 0

                for event in batch:
                    if not isinstance(event, dict):
                        continue

                    event_id = str(event.get("id") or "")

                    if not event_id or event_id in seen:
                        continue

                    seen.add(event_id)
                    events.append(event)
                    new_count += 1

                    if len(events) >= limit:
                        break

                self.stdout.write(
                    f"  取得: {len(batch)}件 / "
                    f"新規ID: {new_count}件 / "
                    f"累計: {len(events)}件"
                )

                if len(batch) < page_size:
                    break

                if new_count == 0:
                    self.stdout.write(
                        "新規IDが増えないため停止"
                    )
                    break

                page += 1
                time.sleep(1.2)

        finally:
            session.close()

        # ============================================
        # Convert and filter
        # ============================================

        rows = []

        excluded = Counter()

        for event in events:

            if event.get("cancelled") is True:
                excluded["cancelled"] += 1
                continue

            if event.get("published") is not True:
                excluded["unpublished"] += 1
                continue

            if event.get("visible") is not True:
                excluded["invisible"] += 1
                continue

            row = transform_event(event)

            if not row["title"] or not row["begin"]:
                excluded["missing_required"] += 1
                continue

            rows.append(row)

        rows.sort(
            key=lambda item: (
                -item["score"],
                str(item["begin"]),
                item["title"],
            )
        )

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        all_file = (
            OUTPUT_DIR / "eventfrog_candidates_all.csv"
        )

        high_file = (
            OUTPUT_DIR / "eventfrog_candidates_priority.csv"
        )

        # Raw API snapshot helps us inspect location and
        # category structures without repeated requests.
        raw_file = (
            OUTPUT_DIR / "eventfrog_raw.json"
        )

        with raw_file.open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                events,
                f,
                ensure_ascii=False,
                indent=2,
            )

        with all_file.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=CSV_FIELDS,
            )
            writer.writeheader()
            writer.writerows(rows)

        priority_rows = [
            row
            for row in rows
            if row["priority"] in ("HIGH", "MEDIUM")
        ]

        with high_file.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=CSV_FIELDS,
            )
            writer.writeheader()
            writer.writerows(priority_rows)

        counts = Counter(
            row["priority"]
            for row in rows
        )

        self.stdout.write(
            "\n=============================="
        )

        self.stdout.write(
            f"API取得: {len(events)}件"
        )

        self.stdout.write(
            f"分析対象: {len(rows)}件"
        )

        for priority in ("HIGH", "MEDIUM", "LOW"):
            self.stdout.write(
                f"{priority}: {counts[priority]}"
            )

        self.stdout.write(
            f"除外: {dict(excluded)}"
        )

        self.stdout.write(
            f"\n全候補: {all_file}"
        )

        self.stdout.write(
            f"優先候補: {high_file}"
        )

        self.stdout.write(
            f"API原データ: {raw_file}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "\n完了。Outings DB変更なし。"
            )
        )
