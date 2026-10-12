
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError


BASE_URL = "https://www.pbz.ch/event-kalender/"

KEYWORDS = (
    "mehr anzeigen",
    "load-more",
    "load_more",
    "loadmore",
    "pagination",
    "ajax",
    "offset",
    "paged",
    "per_page",
    "next-page",
)


class Command(BaseCommand):

    help = "Inspect PBZ pagination without saving data"

    def add_arguments(self, parser):

        parser.add_argument(
            "--month",
            default="202611",
        )

    def handle(self, *args, **options):

        month = options["month"]

        if not re.fullmatch(r"\d{6}", month):
            raise CommandError(
                "年月はYYYYMM形式で指定してください。"
            )

        if not 1 <= int(month[4:]) <= 12:
            raise CommandError("月が正しくありません。")

        url = f"{BASE_URL}?date={month}&view=list"

        self.stdout.write(f"\nURL: {url}")

        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": "YappOutingsResearch/0.1"
                },
                timeout=20,
            )
            response.raise_for_status()

        except requests.RequestException as error:
            raise CommandError(str(error))

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        self.stdout.write(
            f"HTTP: {response.status_code}"
        )

        # ============================================
        # Buttons
        # ============================================

        self.stdout.write(
            "\n========== BUTTONS =========="
        )

        for element in soup.select(
            "button, input[type=button], a"
        ):

            text = element.get_text(
                " ",
                strip=True,
            )

            attributes = str(element.attrs)
            combined = (text + " " + attributes).lower()

            if any(
                keyword in combined
                for keyword in KEYWORDS
            ):

                self.stdout.write(
                    f"\nTEXT: {text[:120]}"
                )

                self.stdout.write(
                    f"TAG: {element.name}"
                )

                self.stdout.write(
                    f"ATTRS: {attributes[:700]}"
                )

                parent = element.parent

                if parent is not None:
                    self.stdout.write(
                        "PARENT: "
                        + str(parent)[:1000]
                    )

        # ============================================
        # Data attributes
        # ============================================

        self.stdout.write(
            "\n========== DATA ATTRIBUTES =========="
        )

        count = 0

        for element in soup.find_all(True):

            data_attrs = {
                key: value
                for key, value in element.attrs.items()
                if key.startswith("data-")
            }

            if not data_attrs:
                continue

            combined = str(data_attrs).lower()

            if any(
                keyword in combined
                for keyword in KEYWORDS
            ):

                self.stdout.write(
                    f"{element.name}: {str(data_attrs)[:900]}"
                )

                count += 1

                if count >= 20:
                    break

        # ============================================
        # JavaScript files
        # ============================================

        self.stdout.write(
            "\n========== JS FILES =========="
        )

        scripts = soup.select("script[src]")

        for script in scripts:

            src = urljoin(
                url,
                script.get("src", ""),
            )

            self.stdout.write(src)

        # ============================================
        # Inline scripts
        # ============================================

        self.stdout.write(
            "\n========== INLINE SCRIPT MATCHES =========="
        )

        found = 0

        for script in soup.select("script:not([src])"):

            content = script.get_text(
                " ",
                strip=True,
            )

            if not content:
                continue

            for keyword in KEYWORDS:

                match = re.search(
                    re.escape(keyword),
                    content,
                    re.IGNORECASE,
                )

                if not match:
                    continue

                start = max(0, match.start() - 160)
                end = min(
                    len(content),
                    match.end() + 300,
                )

                self.stdout.write(
                    f"\nKEYWORD: {keyword}"
                )

                self.stdout.write(
                    content[start:end]
                )

                found += 1

                if found >= 15:
                    break

            if found >= 15:
                break

        self.stdout.write(
            "\n解析完了。DB変更なし。"
        )
