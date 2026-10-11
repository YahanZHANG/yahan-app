
import re
import time
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString

from django.core.management.base import BaseCommand


PBZ_URL = "https://www.pbz.ch/event-kalender/"

MONTHS = {
    "Januar": 1,
    "Februar": 2,
    "März": 3,
    "Maerz": 3,
    "April": 4,
    "Mai": 5,
    "Juni": 6,
    "Juli": 7,
    "August": 8,
    "September": 9,
    "Oktober": 10,
    "November": 11,
    "Dezember": 12,
}

WEEKDAYS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)

TIME_PATTERN = re.compile(
    r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})"
)

HEADERS = {
    "User-Agent": "YappOutingsResearch/0.1 (manual preview)",
    "Accept": "text/html",
}


def clean_text(value):
    return re.sub(r"\s+", " ", value).strip()


def extract_lines(soup):
    """
    h1からイベント本文を取り出す。
    ページ共通のヘルプ欄以降は除外。
    """

    heading = soup.find("h1")

    if heading is None:
        return []

    lines = []

    for node in heading.next_elements:

        if getattr(node, "name", None) == "h2":
            heading_text = clean_text(
                node.get_text(" ", strip=True)
            )

            if "Sie benötigen Hilfe" in heading_text:
                break

        if not isinstance(node, NavigableString):
            continue

        text = clean_text(str(node))

        if text and text not in ("Home", "Eventkalender"):
            lines.append(text)

    return lines


def parse_event(soup, url, year, selected_month):

    heading = soup.find("h1")

    if heading is None:
        return None

    title = clean_text(
        heading.get_text(" ", strip=True)
    )

    lines = extract_lines(soup)

    day = None
    month = None
    time_index = None
    start_at = None
    end_at = None
    venue = ""

    # ---------------------------------------------
    # Day / month / time / venue
    # ---------------------------------------------

    for index, line in enumerate(lines[:20]):

        if (
            day is None
            and re.fullmatch(r"\d{1,2}", line)
        ):
            day = int(line)
            continue

        if month is None and line in MONTHS:
            month = MONTHS[line]
            continue

        match = TIME_PATTERN.search(line)

        if (
            match
            and any(
                weekday in line
                for weekday in WEEKDAYS
            )
        ):
            time_index = index

            if index + 1 < len(lines):
                venue = lines[index + 1]

            if day is not None and month is not None:
                try:
                    event_date = date(year, month, day)

                    # 月をまたぐイベント一覧への対策
                    if month == 12 and selected_month == 1:
                        event_date = date(
                            year - 1, month, day
                        )
                    elif month == 1 and selected_month == 12:
                        event_date = date(
                            year + 1, month, day
                        )

                    start_at = datetime.combine(
                        event_date,
                        datetime.strptime(
                            match.group(1), "%H:%M"
                        ).time(),
                    )

                    end_at = datetime.combine(
                        event_date,
                        datetime.strptime(
                            match.group(2), "%H:%M"
                        ).time(),
                    )

                    if end_at <= start_at:
                        end_at += timedelta(days=1)

                except ValueError:
                    pass

            break

    # ---------------------------------------------
    # Description
    # ---------------------------------------------

    description_lines = []

    if time_index is not None:
        description_lines = lines[time_index + 2:]

    description = "\n".join(description_lines).strip()

    lower_description = description.lower()

    # ---------------------------------------------
    # Fee detection: explicit evidence only
    # ---------------------------------------------

    free_keywords = [
        "eintritt frei",
        "kostenlos",
        "gratis",
        "free –",
        "free -",
        "free,",
        "kurs ist gratis",
    ]

    free_detected = any(
        keyword in lower_description
        for keyword in free_keywords
    )

    # ---------------------------------------------
    # Venue exception warning
    # ---------------------------------------------

    venue_warning = any(
        keyword in lower_description
        for keyword in (
            "findet im ",
            "findet in der ",
            "findet am ",
            "wichtiger hinweis",
            "adresse:",
        )
    )

    # ---------------------------------------------
    # Data quality
    # ---------------------------------------------

    warnings = []

    if not start_at or not end_at:
        warnings.append("日時を確認")

    if not venue:
        warnings.append("会場を確認")

    if venue_warning:
        warnings.append("会場変更・特記事項を確認")

    return {
        "title_original": title,
        "start_at": start_at,
        "end_at": end_at,
        "venue": venue,
        "city": "Zürich",
        "is_free": True if free_detected else None,
        "description_original": description,
        "original_url": url,
        "warnings": warnings,
    }


class Command(BaseCommand):

    help = "Preview structured PBZ events without saving"

    def add_arguments(self, parser):

        parser.add_argument(
            "--month",
            default=date.today().strftime("%Y%m"),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=5,
        )

    def handle(self, *args, **options):

        month_value = options["month"]

        if not re.fullmatch(r"\d{6}", month_value):
            self.stderr.write(
                "月はYYYYMM形式で指定して。"
            )
            return

        year = int(month_value[:4])
        month_number = int(month_value[4:])

        if not 1 <= month_number <= 12:
            self.stderr.write("月が正しくない。")
            return

        limit = max(
            1,
            min(options["limit"], 10),
        )

        list_url = (
            f"{PBZ_URL}?date={month_value}&view=list"
        )

        session = requests.Session()
        session.headers.update(HEADERS)

        try:

            response = session.get(
                list_url,
                timeout=20,
            )
            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            event_urls = []
            seen = set()

            for anchor in soup.select("a[href]"):

                url = urljoin(
                    list_url,
                    anchor["href"],
                )

                parsed = urlparse(url)

                if parsed.hostname not in (
                    "pbz.ch",
                    "www.pbz.ch",
                ):
                    continue

                if not parsed.path.startswith("/event/"):
                    continue

                url = (
                    f"{parsed.scheme}://"
                    f"{parsed.netloc}"
                    f"{parsed.path}"
                )

                if url in seen:
                    continue

                seen.add(url)
                event_urls.append(url)

            self.stdout.write(
                f"\nイベントURL: {len(event_urls)}件"
            )

            for index, url in enumerate(
                event_urls[:limit],
                start=1,
            ):

                if index > 1:
                    time.sleep(1.5)

                try:
                    response = session.get(
                        url,
                        timeout=20,
                    )
                    response.raise_for_status()

                except requests.RequestException as error:
                    self.stderr.write(
                        f"取得失敗: {error}"
                    )
                    continue

                detail_soup = BeautifulSoup(
                    response.text,
                    "html.parser",
                )

                event = parse_event(
                    detail_soup,
                    url,
                    year,
                    month_number,
                )

                if event is None:
                    continue

                self.stdout.write(
                    f"\n{'=' * 50}"
                )
                self.stdout.write(
                    f"[{index}] {event['title_original']}"
                )

                self.stdout.write(
                    f"開始: {event['start_at'] or '不明'}"
                )
                self.stdout.write(
                    f"終了: {event['end_at'] or '不明'}"
                )
                self.stdout.write(
                    f"会場: {event['venue'] or '不明'}"
                )

                fee = (
                    "無料（本文で確認）"
                    if event["is_free"] is True
                    else "不明"
                )

                self.stdout.write(
                    f"料金: {fee}"
                )

                self.stdout.write(
                    f"URL: {event['original_url']}"
                )

                if event["warnings"]:
                    self.stdout.write(
                        "要確認: "
                        + " / ".join(event["warnings"])
                    )
                else:
                    self.stdout.write("要確認: なし")

                self.stdout.write(
                    "説明: "
                    + event["description_original"][:350]
                )

            self.stdout.write(
                "\nプレビュー完了。DB変更なし。"
            )

        finally:
            session.close()
