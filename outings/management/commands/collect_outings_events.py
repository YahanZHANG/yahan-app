
from datetime import date
from collections import Counter


from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from outings.collectors.pbz import PBZCollector
from outings.collectors.ggg_basel import GGGBaselCollector

from outings.collectors.storage import (
    save_collected_event,
)


COLLECTORS = {
    "pbz": PBZCollector,
    "ggg_basel": GGGBaselCollector,
}


class Command(BaseCommand):

    help = "Collect events from configured sources"

    def add_arguments(self, parser):

        parser.add_argument(
            "--source",
            choices=sorted(COLLECTORS.keys()),
            required=True,
        )

        parser.add_argument(
            "--month",
            default=date.today().strftime("%Y%m"),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=5,
        )

        parser.add_argument(
            "--commit",
            action="store_true",
        )

    def handle(self, *args, **options):

        source_key = options["source"]
        month = options["month"]
        limit = options["limit"]
        commit = options["commit"]

        collector = COLLECTORS[source_key]()

        self.stdout.write(
            f"\n収集元: {collector.source_name}"
        )

        self.stdout.write(
            f"対象月: {month}"
        )

        self.stdout.write(
            "モード: "
            + ("下書き保存" if commit else "プレビュー")
        )

        try:
            events = collector.collect(
                month=month,
                limit=limit,
            )

        except (ValueError, Exception) as error:
            raise CommandError(
                f"イベント収集失敗: {error}"
            ) from error

        self.stdout.write(
            f"\n取得イベント数: {len(events)}"
        )

        counts = Counter()

        for index, item in enumerate(events, start=1):

            self.stdout.write(
                f"\n[{index}] {item.title or '(取得失敗)'}"
            )

            self.stdout.write(
                f"日時: {item.start_at} ～ {item.end_at}"
            )

            self.stdout.write(
                f"会場: {item.venue}"
            )

            self.stdout.write(
                f"URL: {item.original_url}"
            )

            status, event_id = save_collected_event(
                item,
                commit=commit,
            )

            counts[status] += 1

            self.stdout.write(
                f"結果: {status}"
                + (
                    f" / Event ID {event_id}"
                    if event_id
                    else ""
                )
            )

            if item.warnings:
                self.stdout.write(
                    "注意: "
                    + " / ".join(item.warnings)
                )

        self.stdout.write(
            "\n=============================="
        )

        for status in (
            "CREATED",
            "EXISTS",
            "DRY_RUN",
            "REVIEW",
            "INVALID",
        ):
            self.stdout.write(
                f"{status}: {counts[status]}"
            )

        self.stdout.write(
            "\n処理完了。"
        )
