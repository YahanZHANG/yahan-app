
import csv
import json
import re
import time

from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from outings.management.commands.outings_audit_batch02 import (
    SOURCES_BATCH_02,
)

# =========================================================
# First 20 sources
# =========================================================

SOURCES = [
    ("ZH", "PBZ Zürich",
     "https://www.pbz.ch/event-kalender/"),

    ("ZH", "Zürcher Museen",
     "https://zuercher-museen.ch/agenda"),

    ("ZH", "Schule+Kultur Zürich",
     "https://www.schuleundkultur.zh.ch/angebot/alle-veranstaltungen"),

    ("BS", "GGG Stadtbibliothek Basel",
     "https://www.stadtbibliothekbasel.ch/de/veranstaltungen.html"),

    ("BS", "Basel Tourism",
     "https://www.basel.com/de/veranstaltungskalender"),

    ("ZG", "Kanton Zug Veranstaltungen",
     "https://veranstaltungen.zug.ch/events"),

    ("ZG", "Kunsthaus Zug",
     "https://kunsthauszug.ch/de/events"),

    ("ZG", "Zug Tourismus",
     "https://www.zug-tourismus.ch/de/veranstaltungen/"),

    ("ZH", "Stadt Winterthur",
     "https://stadt.winterthur.ch/veranstaltungen"),

    ("ZH", "Naturmuseum Winterthur",
     "https://natur.winterthur.ch/veranstaltungen"),

    ("ZH", "Kunst Museum Winterthur",
     "https://www.kmw.ch/agenda/alle-veranstaltungen/"),

    ("ZH", "Fotomuseum Winterthur",
     "https://www.fotomuseum.ch/de/events/"),

    ("LU", "Bibliotheksverband Region Luzern",
     "https://bvl.ch/veranstaltungen"),

    ("AG", "Museum Aargau",
     "https://www.museumaargau.ch/veranstaltungen"),

    ("AG", "Naturama Aargau",
     "https://www.naturama.ch/agenda"),

    ("BE", "Museen Bern",
     "https://www.museen-bern.ch/de/ausstellungen"),

    ("BE", "Bern Welcome",
     "https://bern.com/de/aktuelles/veranstaltungskalender"),

    ("JP", "チューリッヒ日本人会",
     "https://japanswiss.ch/"),

    ("JP", "チューリッヒ日本人学校",
     "https://jszurich.ch/"),

    ("JP", "UZH Japanologie",
     "https://www.aoi.uzh.ch/en/japanologie/agenda.html"),
]


EVENT_WORDS = (
    "event",
    "veranstaltung",
    "agenda",
    "kalender",
    "workshop",
    "lesung",
    "führung",
    "festival",
)

DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}\.\d{1,2}\.\d{4}"
    r"|"
    r"\d{4}-\d{2}-\d{2}"
    r")\b"
)


# =========================================================
# Extract diagnostic signals
# =========================================================

def inspect_page(html, page_url):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    title = ""

    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True,
        )

    main = soup.select_one("main") or soup.body or soup

    visible_text = main.get_text(
        " ",
        strip=True,
    )

    date_matches = DATE_PATTERN.findall(
        visible_text,
    )

    event_links = set()

    for anchor in main.select("a[href]"):

        href = urljoin(
            page_url,
            anchor.get("href", ""),
        )

        parsed = urlparse(href)

        if parsed.scheme not in (
            "http",
            "https",
        ):
            continue

        link_text = anchor.get_text(
            " ",
            strip=True,
        ).lower()

        combined = (
            parsed.path.lower()
            + " "
            + link_text
        )

        if any(
            word in combined
            for word in EVENT_WORDS
        ):
            event_links.add(href.split("#")[0])

    jsonld_events = 0

    def visit(value):

        nonlocal jsonld_events

        if isinstance(value, list):
            for item in value:
                visit(item)
            return

        if not isinstance(value, dict):
            return

        types = value.get("@type", [])

        if isinstance(types, str):
            types = [types]

        if any(
            str(item).split("/")[-1].lower() == "event"
            for item in types
        ):
            jsonld_events += 1

        for nested in value.values():
            if isinstance(nested, (list, dict)):
                visit(nested)

    for script in soup.select(
        'script[type="application/ld+json"]'
    ):

        try:
            visit(json.loads(script.get_text()))
        except (ValueError, TypeError):
            pass

    return {
        "page_title": title,
        "date_signals": len(date_matches),
        "event_link_signals": len(event_links),
        "jsonld_events": jsonld_events,
    }


# =========================================================
# Management command
# =========================================================

class Command(BaseCommand):

    help = "Audit 20 event sources without database changes"

    def add_arguments(self, parser):

        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
        )

        parser.add_argument(
            "--delay",
            type=float,
            default=1.5,
        )

        parser.add_argument(
            "--batch",
            type=int,
            choices=[1, 2],
            default=1,
        )

    def handle(self, *args, **options):


        batch_number = options["batch"]

        sources = (
            SOURCES
            if batch_number == 1
            else SOURCES_BATCH_02
        )

        batch_size = options["batch_size"]
        
        delay = options["delay"]

        if not 1 <= batch_size <= len(sources):
            raise CommandError(
                f"batch-sizeは1〜{len(sources)}"
            )

        if delay < 0:
            raise CommandError(
                "delayは0以上にしてください"
            )

        rows = []

        session = requests.Session()

        session.headers.update({
            "User-Agent": (
                "YappOutingsResearch/0.1 "
                "(source compatibility audit)"
            ),
            "Accept": "text/html",
        })

        targets = sources[:batch_size]

        try:

            for index, (
                region,
                name,
                url,
            ) in enumerate(targets, start=1):

                self.stdout.write(
                    f"\n[{index}/{len(targets)}] {name}"
                )

                row = {
                    "region": region,
                    "name": name,
                    "url": url,
                    "final_url": "",
                    "http_status": "",
                    "result": "",
                    "page_title": "",
                    "date_signals": 0,
                    "event_link_signals": 0,
                    "jsonld_events": 0,
                    "error": "",
                    "checked_at": (
                        datetime.now().astimezone().isoformat()
                    ),
                }

                try:

                    response = session.get(
                        url,
                        timeout=15,
                        allow_redirects=True,
                    )

                    row["http_status"] = (
                        response.status_code
                    )

                    row["final_url"] = response.url

                    response.raise_for_status()

                    content_type = response.headers.get(
                        "Content-Type", ""
                    ).lower()

                    if "html" not in content_type:
                        row["result"] = "UNSUPPORTED_FORMAT"

                    else:
                        info = inspect_page(
                            response.text,
                            response.url,
                        )

                        row.update(info)

                        if (
                            info["jsonld_events"] > 0
                            or info["date_signals"] > 0
                            or info["event_link_signals"] > 0
                        ):
                            row["result"] = "PARSER_NEEDED"
                        else:
                            row["result"] = "NO_SIGNALS"

                except requests.RequestException as error:

                    row["result"] = "FETCH_ERROR"
                    row["error"] = str(error)[:400]

                except Exception as error:

                    row["result"] = "PARSER_ERROR"
                    row["error"] = str(error)[:400]

                rows.append(row)

                self.stdout.write(
                    f"結果: {row['result']}"
                )

                self.stdout.write(
                    f"HTTP: {row['http_status']}"
                )

                self.stdout.write(
                    f"日時の手がかり: {row['date_signals']}"
                )

                self.stdout.write(
                    f"イベントリンク候補: "
                    f"{row['event_link_signals']}"
                )

                self.stdout.write(
                    f"JSON-LDイベント: "
                    f"{row['jsonld_events']}"
                )

                if row["error"]:
                    self.stdout.write(
                        f"ERROR: {row['error']}"
                    )

                if index < len(targets):
                    time.sleep(delay)

        finally:
            session.close()

        # =================================================
        # Write report to local CSV
        # =================================================

        output_dir = Path("outings_audit")
        output_dir.mkdir(exist_ok=True)

        output_file = (
            output_dir
            / f"outings_sources_batch{batch_number:02d}.csv"
        )

        fieldnames = [
            "region",
            "name",
            "url",
            "final_url",
            "http_status",
            "result",
            "page_title",
            "date_signals",
            "event_link_signals",
            "jsonld_events",
            "error",
            "checked_at",
        ]

        with output_file.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(
            "\n================================"
        )

        self.stdout.write(
            f"診断サイト数: {len(rows)}"
        )

        for result in (
            "PARSER_NEEDED",
            "NO_SIGNALS",
            "FETCH_ERROR",
            "PARSER_ERROR",
            "UNSUPPORTED_FORMAT",
        ):

            count = sum(
                row["result"] == result
                for row in rows
            )

            self.stdout.write(
                f"{result}: {count}"
            )

        self.stdout.write(
            f"\nCSV: {output_file}"
        )

        self.stdout.write(
            "DB変更なし。イベント登録なし。"
        )
