
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from outings.collectors.base import CollectedEvent


class GGGBaselCollector:

    source_name = "GGG Stadtbibliothek Basel"

    base_url = (
        "https://www.stadtbibliothekbasel.ch/"
        "de/veranstaltungen.html"
    )

    DATE_PATTERN = re.compile(
        r"(?P<day>\d{2}\.\d{2}\.\d{4})"
        r"\s+"
        r"(?P<start>\d{2}:\d{2})"
        r"\s*[-–]\s*"
        r"(?:(?P<end_day>\d{2}\.\d{2}\.\d{4})\s+)?"
        r"(?P<end>\d{2}:\d{2})"
    )

    def parse_date(self, day, clock):
        return datetime.strptime(
            f"{day} {clock}",
            "%d.%m.%Y %H:%M",
        )

    def get_event_container(self, heading):

        # Locate a reasonably small card containing
        # both its heading and its date/time.
        for parent in heading.parents:

            if parent.name in (
                "body",
                "html",
                "main",
            ):
                break

            text = parent.get_text(
                " ",
                strip=True,
            )

            if (
                self.DATE_PATTERN.search(text)
                and len(text) <= 1800
            ):
                return parent

        return None

    def extract_detail_url(self, heading, card):

        anchor = heading.find_parent(
            "a",
            href=True,
        )

        if anchor is None:
            anchor = heading.find(
                "a",
                href=True,
            )

        if anchor is None:
            for candidate in card.select("a[href]"):
                label = candidate.get_text(
                    " ",
                    strip=True,
                ).lower()

                if label in (
                    "mehr",
                    "details",
                    "weiterlesen",
                ):
                    anchor = candidate
                    break

        if anchor is None:
            return ""

        url = urljoin(
            self.base_url,
            anchor["href"],
        )

        parsed = urlparse(url)

        if parsed.hostname not in (
            "stadtbibliothekbasel.ch",
            "www.stadtbibliothekbasel.ch",
        ):
            return ""

        if parsed.path.rstrip("/") == (
            "/de/veranstaltungen.html"
        ):
            return ""

        return url.split("#")[0]

    def extract_card(self, heading):

        card = self.get_event_container(heading)

        if card is None:
            return None

        title = heading.get_text(
            " ",
            strip=True,
        )

        text = card.get_text(
            "\n",
            strip=True,
        )

        match = self.DATE_PATTERN.search(text)

        if match is None:
            return None

        start_at = self.parse_date(
            match.group("day"),
            match.group("start"),
        )

        end_at = self.parse_date(
            match.group("end_day")
            or match.group("day"),
            match.group("end"),
        )

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        # Find venue between date line and title.
        venue = ""

        title_index = next(
            (
                i for i, line in enumerate(lines)
                if title in line
            ),
            None,
        )

        if title_index is not None:

            preceding = lines[:title_index]

            for line in reversed(preceding):

                if (
                    line.startswith("GGG ")
                    or line.startswith("Bibliothek ")
                    or line.startswith("Quartiertreffpunkt ")
                ):
                    venue = line
                    break

        detail_url = self.extract_detail_url(
            heading,
            card,
        )

        warnings = []

        if not detail_url:
            warnings.append(
                "イベント詳細URLを確認"
            )

        if not venue:
            warnings.append(
                "会場を確認"
            )

        if end_at <= start_at:
            warnings.append(
                "開催日時を確認"
            )

        # Unknown fee stays unknown.
        free = None

        description = text

        if re.search(
            r"eintritt frei|kostenlos|gratis|free of charge",
            text,
            re.IGNORECASE,
        ):
            free = True

        elif re.search(
            r"eintritt\s*:\s*\d|CHF\s*\d",
            text,
            re.IGNORECASE,
        ):
            free = False

        return CollectedEvent(
            source_name=self.source_name,
            external_id=(
                urlparse(detail_url).path.strip("/")
                if detail_url else ""
            ),
            title=title,
            original_url=detail_url,
            start_at=start_at,
            end_at=end_at,
            description=description,
            venue=venue,
            city="Basel",
            canton="BS",
            is_free=free,
            warnings=warnings,
        )

    def collect(self, month, limit=5):

        if not re.fullmatch(r"\d{6}", month):
            raise ValueError(
                "年月はYYYYMM形式で指定してください"
            )

        year = int(month[:4])
        month_number = int(month[4:])

        if not 1 <= month_number <= 12:
            raise ValueError("月が正しくありません")

        if not 1 <= limit <= 50:
            raise ValueError(
                "limitは1〜50で指定してください"
            )

        session = requests.Session()

        session.headers.update({
            "User-Agent": (
                "YappOutingsResearch/0.1 "
                "(manual metadata preview)"
            ),
            "Accept": "text/html",
        })

        results = []
        seen = set()

        try:

            for page in range(1, 11):

                if page > 1:
                    time.sleep(1.5)

                response = session.get(
                    self.base_url,
                    params={"page": page},
                    timeout=20,
                )
                response.raise_for_status()

                soup = BeautifulSoup(
                    response.text,
                    "html.parser",
                )

                page_events = []

                for heading in soup.select("h3"):

                    event = self.extract_card(
                        heading
                    )

                    if event is None:
                        continue

                    if not (
                        event.start_at
                        and event.start_at.year == year
                        and event.start_at.month == month_number
                    ):
                        continue

                    # Avoid duplicate event cards.
                    key = (
                        event.original_url,
                        event.start_at,
                        event.title,
                    )

                    if key in seen:
                        continue

                    seen.add(key)
                    page_events.append(event)

                if not page_events and page >= 3:
                    break

                results.extend(page_events)

                if len(results) >= limit:
                    break

            return results[:limit]

        finally:
            session.close()
