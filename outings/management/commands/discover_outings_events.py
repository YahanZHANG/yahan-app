
import csv
import re
import time

from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError

from outings.management.commands.audit_outings_sources import (
    SOURCES as SOURCES_BATCH_01,
)
from outings.management.commands.outings_audit_batch02 import (
    SOURCES_BATCH_02,
)


DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}\.\d{1,2}\.\d{2,4}"
    r"|"
    r"\d{4}-\d{2}-\d{2}"
    r"|"
    r"\d{1,2}\.\s*"
    r"(?:Januar|Februar|März|April|Mai|Juni|"
    r"Juli|August|September|Oktober|November|Dezember)"
    r")\b",
    re.IGNORECASE,
)

EVENT_KEYWORDS = (
    "event",
    "veranstaltung",
    "agenda",
    "workshop",
    "führung",
    "fuehrung",
    "lesung",
    "festival",
    "konzert",
    "theater",
    "ausstellung",
    "familien",
    "kinder",
    "programme",
    "programm",
    "erlebnis",
    "行事",
    "イベント",
    "講演",
    "祭り",
    "交流会",
)

EXCLUDE_PATHS = (
    "/wp-admin/",
    "/wp-content/",
    "/assets/",
    "/static/",
    "/login",
    "/datenschutz",
    "/impressum",
    "/privacy",
    "/kontakt",
)

EXCLUDE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp",
    ".svg", ".gif", ".pdf", ".zip",
    ".mp4", ".css", ".js",
)

HEADERS = {
    "User-Agent": (
        "YappOutingsResearch/0.1 "
        "(manual event-source evaluation)"
    ),
    "Accept": "text/html",
}


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def is_valid_url(url):
    parsed = urlparse(url)

    return (
        parsed.scheme in ("http", "https")
        and bool(parsed.hostname)
        and not parsed.path.lower().endswith(
            EXCLUDE_EXTENSIONS
        )
        and not any(
            part in parsed.path.lower()
            for part in EXCLUDE_PATHS
        )
    )


def discover_candidates(html, page_url, limit=30):

    soup = BeautifulSoup(html, "html.parser")

    main = (
        soup.select_one("main")
        or soup.select_one("#content")
        or soup.body
        or soup
    )

    candidates = []
    seen = set()

    page_host = urlparse(page_url).hostname or ""

    for anchor in main.select("a[href]"):

        href = anchor.get("href", "").strip()

        if (
            not href
            or href.startswith(("#", "mailto:", "tel:", "javascript:"))
        ):
            continue

        url = urljoin(page_url, href).split("#")[0]

        if not is_valid_url(url):
            continue

        parsed = urlparse(url)

        # Prefer links on the same site.
        # Cross-domain source links can be reviewed separately.
        if (
            parsed.hostname != page_host
            and not (
                parsed.hostname or ""
            ).endswith("." + page_host)
        ):
            continue

        title = clean_text(
            anchor.get_text(" ", strip=True)
        )

        if not title:
            title = clean_text(
                anchor.get("aria-label", "")
            )

        if not title:
            continue

        path = parsed.path.lower()

        keyword_match = any(
            word in (path + " " + title.lower())
            for word in EVENT_KEYWORDS
        )

        # Look for nearby dates, without traversing
        # the entire page.
        context = ""
        date_text = ""

        for parent in list(anchor.parents)[:4]:

            if parent.name in ("body", "main", "html"):
                break

            text = clean_text(
                parent.get_text(" ", strip=True)
            )

            if len(text) > 1200:
                continue

            context = text

            found = DATE_PATTERN.search(text)

            if found:
                date_text = found.group(0)
                break

        # Candidate, not a verified event.
        if not keyword_match and not date_text:
            continue

        key = url.rstrip("/")

        if key in seen:
            continue

        seen.add(key)

        # A date near the link is a stronger signal,
        # but not proof that it belongs to the event.
        confidence = (
            "DATE_AND_KEYWORD"
            if date_text and keyword_match
            else "DATE_ONLY"
            if date_text
            else "KEYWORD_ONLY"
        )

        candidates.append({
            "title_candidate": title[:250],
            "event_url_candidate": url,
            "date_candidate": date_text,
            "confidence": confidence,
            "context_excerpt": context[:450],
        })

    priority = {
        "DATE_AND_KEYWORD": 0,
        "DATE_ONLY": 1,
        "KEYWORD_ONLY": 2,
    }

    candidates.sort(
        key=lambda item: priority[item["confidence"]]
    )

    return candidates[:limit]


class Command(BaseCommand):

    help = (
        "Discover event links from 20 sources "
        "without changing the database"
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--batch",
            type=int,
            choices=(1, 2),
            default=1,
        )

        parser.add_argument(
            "--limit-per-source",
            type=int,
            default=30,
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

        if not 1 <= limit <= 100:
            raise CommandError(
                "--limit-per-source は1〜100で指定"
            )

        if delay < 1:
            raise CommandError(
                "--delay は1秒以上で指定"
            )

        sources = (
            SOURCES_BATCH_01
            if batch == 1
            else SOURCES_BATCH_02
        )

        output_dir = Path("outings_audit")
        output_dir.mkdir(parents=True, exist_ok=True)

        candidates_file = (
            output_dir
            / f"outings_candidates_batch{batch:02d}.csv"
        )

        summary_file = (
            output_dir
            / f"outings_discovery_batch{batch:02d}.csv"
        )

        candidate_rows = []
        summary_rows = []

        session = requests.Session()
        session.headers.update(HEADERS)

        try:

            for index, (
                region,
                name,
                url,
            ) in enumerate(sources, start=1):

                self.stdout.write(
                    f"\n[{index}/{len(sources)}] {name}"
                )

                checked_at = (
                    datetime.now().astimezone().isoformat()
                )

                summary = {
                    "region": region,
                    "source": name,
                    "source_url": url,
                    "status": "",
                    "http_status": "",
                    "candidate_count": 0,
                    "error": "",
                    "checked_at": checked_at,
                }

                try:

                    response = session.get(
                        url,
                        timeout=20,
                        allow_redirects=True,
                    )

                    summary["http_status"] = (
                        response.status_code
                    )

                    response.raise_for_status()

                    content_type = response.headers.get(
                        "Content-Type", ""
                    ).lower()

                    if "html" not in content_type:
                        summary["status"] = (
                            "UNSUPPORTED_FORMAT"
                        )

                    else:

                        candidates = discover_candidates(
                            response.text,
                            response.url,
                            limit=limit,
                        )

                        for item in candidates:
                            candidate_rows.append({
                                "region": region,
                                "source": name,
                                "source_url": url,
                                **item,
                            })

                        summary["candidate_count"] = (
                            len(candidates)
                        )

                        summary["status"] = (
                            "CANDIDATES_FOUND"
                            if candidates
                            else "NO_CANDIDATES"
                        )

                except requests.RequestException as error:
                    summary["status"] = "FETCH_ERROR"
                    summary["error"] = str(error)[:350]

                except Exception as error:
                    summary["status"] = "PARSE_ERROR"
                    summary["error"] = str(error)[:350]

                summary_rows.append(summary)

                self.stdout.write(
                    f"結果: {summary['status']}"
                )

                self.stdout.write(
                    f"候補: {summary['candidate_count']}件"
                )

                if summary["error"]:
                    self.stdout.write(
                        f"ERROR: {summary['error']}"
                    )

                if index < len(sources):
                    time.sleep(delay)

        finally:
            session.close()

        with candidates_file.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            fields = [
                "region",
                "source",
                "source_url",
                "title_candidate",
                "event_url_candidate",
                "date_candidate",
                "confidence",
                "context_excerpt",
            ]

            writer = csv.DictWriter(
                file,
                fieldnames=fields,
            )
            writer.writeheader()
            writer.writerows(candidate_rows)

        with summary_file.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            fields = [
                "region",
                "source",
                "source_url",
                "status",
                "http_status",
                "candidate_count",
                "error",
                "checked_at",
            ]

            writer = csv.DictWriter(
                file,
                fieldnames=fields,
            )
            writer.writeheader()
            writer.writerows(summary_rows)

        self.stdout.write(
            "\n=============================="
        )

        self.stdout.write(
            f"対象情報源: {len(sources)}"
        )

        self.stdout.write(
            f"イベントURL候補: {len(candidate_rows)}"
        )

        self.stdout.write(
            f"候補CSV: {candidates_file}"
        )

        self.stdout.write(
            f"結果CSV: {summary_file}"
        )

        self.stdout.write(
            "DB変更なし。イベント登録なし。"
        )
