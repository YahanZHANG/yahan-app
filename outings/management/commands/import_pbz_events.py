
import time
from datetime import date
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from outings.models import (
    Event,
    EventLocation,
    EventOccurrence,
    EventSource,
)

from outings.management.commands.preview_pbz_events import (
    PBZ_URL,
    parse_event,
)


SOURCE_NAME = "PBZ Zürich"
SWISS_TIMEZONE = ZoneInfo("Europe/Zurich")


class Command(BaseCommand):

    help = "Import PBZ events as drafts. Dry-run by default."

    def add_arguments(self, parser):

        parser.add_argument(
            "--month",
            default=timezone.localdate().strftime("%Y%m"),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=5,
        )

        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually save events to the database",
        )

    def handle(self, *args, **options):

        month_value = options["month"]
        limit = options["limit"]
        commit = options["commit"]

        if (
            len(month_value) != 6
            or not month_value.isdigit()
        ):
            raise CommandError(
                "月はYYYYMM形式で指定してください。"
            )

        year = int(month_value[:4])
        month_number = int(month_value[4:])

        try:
            date(year, month_number, 1)
        except ValueError:
            raise CommandError("年月が正しくありません。")

        if not 1 <= limit <= 10:
            raise CommandError(
                "--limit は1〜10で指定してください。"
            )

        source = EventSource.objects.filter(
            name=SOURCE_NAME
        ).first()

        if source is None:
            raise CommandError(
                "PBZ Zürich がEventSourceにありません。"
                " seed_outings_sourcesを実行してください。"
            )

        list_url = (
            f"{PBZ_URL}?date={month_value}&view=list"
        )

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "YappOutingsResearch/0.1 "
                "(manual import validation)"
            ),
            "Accept": "text/html",
        })

        created_count = 0
        skipped_count = 0
        existing_count = 0

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

                clean_url = (
                    f"{parsed.scheme}://"
                    f"{parsed.netloc}"
                    f"{parsed.path}"
                )

                if clean_url in seen:
                    continue

                seen.add(clean_url)
                event_urls.append(clean_url)

            self.stdout.write(
                f"イベントURL: {len(event_urls)}件"
            )

            self.stdout.write(
                "モード: "
                + ("DB保存" if commit else "プレビュー")
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

                    detail_soup = BeautifulSoup(
                        response.text,
                        "html.parser",
                    )

                except requests.RequestException as error:

                    self.stderr.write(
                        f"取得失敗: {url} / {error}"
                    )

                    skipped_count += 1
                    continue

                data = parse_event(
                    detail_soup,
                    url,
                    year,
                    month_number,
                )

                if data is None:
                    skipped_count += 1
                    continue

                title = data["title_original"]

                self.stdout.write(
                    f"\n[{index}] {title}"
                )

                # --------------------------------------
                # Validate before import
                # --------------------------------------

                if data["warnings"]:

                    self.stdout.write(
                        "SKIP（確認が必要）: "
                        + " / ".join(data["warnings"])
                    )

                    skipped_count += 1
                    continue

                if not data["start_at"] or not data["end_at"]:

                    self.stdout.write(
                        "SKIP（日時不明）"
                    )

                    skipped_count += 1
                    continue

                # URL is stable external identifier
                external_id = urlparse(url).path.strip("/")

                existing = Event.objects.filter(
                    source=source,
                    external_id=external_id,
                ).first()

                if existing is not None:

                    self.stdout.write(
                        f"EXISTS: Event ID {existing.pk}"
                    )

                    existing_count += 1
                    continue

                start_at = timezone.make_aware(
                    data["start_at"],
                    SWISS_TIMEZONE,
                )

                end_at = timezone.make_aware(
                    data["end_at"],
                    SWISS_TIMEZONE,
                )

                if end_at <= start_at:

                    self.stdout.write(
                        "SKIP（終了日時が開始以前）"
                    )

                    skipped_count += 1
                    continue

                self.stdout.write(
                    f"日時: {start_at} - {end_at}"
                )

                self.stdout.write(
                    f"会場: {data['venue']}"
                )

                self.stdout.write(
                    "料金: "
                    + (
                        "無料"
                        if data["is_free"] is True
                        else "要確認"
                    )
                )

                if not commit:

                    self.stdout.write(
                        "DRY-RUN: 保存対象"
                    )

                    continue

                # --------------------------------------
                # Save atomically
                # --------------------------------------

                with transaction.atomic():

                    location, _ = (
                        EventLocation.objects.get_or_create(
                            name=data["venue"],
                            city="Zürich",
                            canton="ZH",
                        )
                    )

                    event = Event.objects.create(
                        title=title,
                        title_original=title,
                        summary_ja="",
                        description_original=(
                            data["description_original"]
                        ),
                        event_type=Event.EventType.ONE_TIME,
                        status=Event.Status.DRAFT,
                        location=location,
                        is_free=(data["is_free"] is True),
                        price_text=(
                            "無料"
                            if data["is_free"] is True
                            else "料金要確認"
                        ),
                        original_url=url,
                        source=source,
                        external_id=external_id,
                    )

                    EventOccurrence.objects.create(
                        event=event,
                        start_at=start_at,
                        end_at=end_at,
                    )

                created_count += 1

                self.stdout.write(
                    f"CREATED: Event ID {event.pk}"
                )

            self.stdout.write(
                "\n=============================="
            )

            self.stdout.write(
                f"新規登録: {created_count}"
            )

            self.stdout.write(
                f"既存: {existing_count}"
            )

            self.stdout.write(
                f"スキップ: {skipped_count}"
            )

            if commit:
                self.stdout.write(
                    self.style.SUCCESS(
                        "下書き登録完了。"
                    )
                )
            else:
                self.stdout.write(
                    "プレビュー完了。DB変更なし。"
                )

        except requests.RequestException as error:

            raise CommandError(
                f"PBZへの接続に失敗: {error}"
            )

        finally:
            session.close()
