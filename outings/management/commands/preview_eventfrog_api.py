
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from django.core.management.base import BaseCommand, CommandError


API_URL = "https://api.eventfrog.net/public/v1/events"
SWISS_TZ = ZoneInfo("Europe/Zurich")


class Command(BaseCommand):
    help = "Preview Eventfrog events without saving anything"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
        )

    def handle(self, *args, **options):
        token = os.environ.get(
            "EVENTFROG_API_TOKEN", ""
        ).strip()

        if not token:
            raise CommandError(
                "EVENTFROG_API_TOKEN が未設定です。"
                "EventfrogのAPI利用手続きを先に確認してください。"
            )

        limit = options["limit"]
        days = options["days"]

        if not 1 <= limit <= 50:
            raise CommandError("--limit は1〜50")

        if not 1 <= days <= 90:
            raise CommandError("--days は1〜90")

        now = datetime.now(SWISS_TZ)
        end = now + timedelta(days=days)

        params = {
            "country": "CH",
            "from": now.isoformat(),
            "to": end.isoformat(),
            "page": 1,
            "perPage": limit,
        }

        self.stdout.write(
            f"対象: スイス / 今後{days}日 / 最大{limit}件"
        )

        try:
            response = requests.get(
                API_URL,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=30,
            )

            if response.status_code in (401, 403):
                raise CommandError(
                    "API認証またはアクセス権限を確認してください。"
                    f" HTTP {response.status_code}"
                )

            response.raise_for_status()
            payload = response.json()

        except requests.RequestException as exc:
            raise CommandError(
                f"API取得失敗: {type(exc).__name__}"
            ) from exc

        except ValueError as exc:
            raise CommandError(
                "APIからJSON以外の応答が返りました"
            ) from exc

        if not isinstance(payload, dict):
            raise CommandError(
                "想定外のJSON形式です"
            )

        events = payload.get("events", [])

        if not isinstance(events, list):
            raise CommandError(
                "events がリスト形式ではありません"
            )

        self.stdout.write(
            f"API内の総件数: "
            f"{payload.get('totalNumberOfResources', '不明')}"
        )
        self.stdout.write(
            f"今回取得した件数: {len(events)}"
        )

        for index, event in enumerate(events, 1):
            if not isinstance(event, dict):
                continue

            title = event.get("title", "")

            if isinstance(title, dict):
                title = (
                    title.get("de")
                    or title.get("en")
                    or title.get("fr")
                    or next(iter(title.values()), "")
                )

            self.stdout.write(
                f"\n[{index}] {str(title)[:150]}"
            )
            self.stdout.write(
                f"ID: {event.get('id', '')}"
            )
            self.stdout.write(
                "利用可能な項目: "
                + ", ".join(sorted(event.keys()))
            )

        self.stdout.write(
            "\nAPIプレビュー完了。DB変更なし。"
        )
