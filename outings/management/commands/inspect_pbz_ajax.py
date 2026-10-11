
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError


BASE_URL = "https://www.pbz.ch/event-kalender/"


class Command(BaseCommand):

    help = "Inspect PBZ load-more AJAX implementation"

    def handle(self, *args, **options):

        session = requests.Session()
        session.headers.update({
            "User-Agent": "YappOutingsResearch/0.1",
        })

        try:
            response = session.get(
                BASE_URL,
                params={
                    "date": "202611",
                    "view": "list",
                },
                timeout=20,
            )
            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            button = soup.select_one(
                'button[data-action="load_more_events"]'
            )

            if button is None:
                raise CommandError(
                    "追加読み込みボタンが見つかりません。"
                )

            self.stdout.write("\n=== BUTTON ===")

            for key, value in button.attrs.items():
                if key.startswith("data-"):
                    self.stdout.write(
                        f"{key}: {value}"
                    )

            self.stdout.write("\n=== JAVASCRIPT ===")

            matched = False

            for script in soup.select("script[src]"):

                script_url = urljoin(
                    BASE_URL,
                    script["src"],
                )

                if "pbz.ch" not in script_url:
                    continue

                js_response = session.get(
                    script_url,
                    timeout=20,
                )
                js_response.raise_for_status()

                content = js_response.text

                for pattern in (
                    "load_more_events",
                    "load-more",
                    "data-offset",
                ):

                    for match in list(
                        re.finditer(
                            re.escape(pattern),
                            content,
                            re.IGNORECASE,
                        )
                    )[:3]:

                        matched = True

                        start = max(
                            0,
                            match.start() - 600,
                        )

                        end = min(
                            len(content),
                            match.end() + 1300,
                        )

                        self.stdout.write(
                            f"\nFILE: {script_url}"
                        )
                        self.stdout.write(
                            f"MATCH: {pattern}"
                        )
                        self.stdout.write(
                            content[start:end]
                        )

            if not matched:
                self.stdout.write(
                    "関連JavaScriptが見つかりませんでした。"
                )

            self.stdout.write(
                "\n解析終了。DB変更なし。"
            )

        except requests.RequestException as error:
            raise CommandError(
                f"通信エラー: {error}"
            )

        finally:
            session.close()
