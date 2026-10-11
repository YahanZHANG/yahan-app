
import re
import time
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from outings.collectors.base import CollectedEvent
from outings.management.commands.preview_pbz_events import (
    parse_event,
)


class PBZCollector:

    source_name = "PBZ Zürich"

    base_url = "https://www.pbz.ch/event-kalender/"

    def collect(self, month, limit=5):

        if not re.fullmatch(r"\d{6}", month):
            raise ValueError("年月はYYYYMM形式で指定")

        year = int(month[:4])
        month_number = int(month[4:])

        date(year, month_number, 1)

        if not 1 <= limit <= 10:
            raise ValueError("limitは1〜10で指定")

        list_url = (
            f"{self.base_url}?date={month}&view=list"
        )

        session = requests.Session()

        session.headers.update({
            "User-Agent": (
                "YappOutingsResearch/0.1 "
                "(manual metadata validation)"
            ),
            "Accept": "text/html",
        })

        results = []

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

            urls = []
            seen = set()

            for anchor in soup.select("a[href]"):

                url = urljoin(
                    list_url,
                    anchor["href"],
                )

                parsed = urlparse(url)

                if parsed.hostname not in (
                    "www.pbz.ch",
                    "pbz.ch",
                ):
                    continue

                if not parsed.path.startswith("/event/"):
                    continue

                clean_url = (
                    f"{parsed.scheme}://"
                    f"{parsed.netloc}"
                    f"{parsed.path}"
                )

                if clean_url in seen:
                    continue

                seen.add(clean_url)
                urls.append(clean_url)

            for index, url in enumerate(urls[:limit]):

                if index:
                    time.sleep(1.5)

                try:
                    response = session.get(
                        url,
                        timeout=20,
                    )
                    response.raise_for_status()

                except requests.RequestException as error:
                    results.append(
                        CollectedEvent(
                            source_name=self.source_name,
                            external_id=urlparse(url).path.strip("/"),
                            title="",
                            original_url=url,
                            warnings=[
                                f"詳細取得失敗: {error}"
                            ],
                        )
                    )
                    continue

                detail = BeautifulSoup(
                    response.text,
                    "html.parser",
                )

                data = parse_event(
                    detail,
                    url,
                    year,
                    month_number,
                )

                if not data:
                    continue

                results.append(
                    CollectedEvent(
                        source_name=self.source_name,
                        external_id=(
                            urlparse(url).path.strip("/")
                        ),
                        title=data["title_original"],
                        original_url=url,
                        start_at=data["start_at"],
                        end_at=data["end_at"],
                        description=(
                            data["description_original"]
                        ),
                        venue=data["venue"],
                        city="Zürich",
                        canton="ZH",
                        is_free=data["is_free"],
                        warnings=list(data["warnings"]),
                    )
                )

        finally:
            session.close()

        return results
