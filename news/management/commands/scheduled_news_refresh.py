import os
from zoneinfo import ZoneInfo

import requests

from django.core.management.base import BaseCommand
from django.utils import timezone


ZURICH_TZ = ZoneInfo(
    "Europe/Zurich"
)


# スイス時間での更新時刻
REFRESH_HOURS = {
    6: "morning",
    11: "late_morning",
    16: "afternoon",
    21: "evening",
}


class Command(BaseCommand):
    help = (
        "Ask the Yahan-app web service to refresh "
        "Swiss news at scheduled Zurich times."
    )


    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Send a refresh request immediately "
                "regardless of Zurich time."
            ),
        )

        parser.add_argument(
            "--period",
            choices=[
                "morning",
                "late_morning",
                "afternoon",
                "evening",
            ],
            default=None,
            help=(
                "Period to use with --force. "
                "If omitted, it is determined "
                "from Zurich time."
            ),
        )


    def handle(
        self,
        *args,
        **options,
    ):
        refresh_url = os.environ.get(
            "NEWS_REFRESH_URL",
            "",
        )

        refresh_token = os.environ.get(
            "NEWS_REFRESH_TOKEN",
            "",
        )


        # ========================================
        # Environment check
        # ========================================

        if not refresh_url:

            self.stderr.write(
                self.style.ERROR(
                    "NEWS_REFRESH_URL is not configured."
                )
            )

            return


        if not refresh_token:

            self.stderr.write(
                self.style.ERROR(
                    "NEWS_REFRESH_TOKEN is not configured."
                )
            )

            return


        # ========================================
        # Zurich local time
        # ========================================

        now_zurich = (
            timezone.now()
            .astimezone(
                ZURICH_TZ
            )
        )


        self.stdout.write(
            (
                "Zurich time: "
                f"{now_zurich:%Y-%m-%d %H:%M:%S %Z}"
            )
        )


        # ========================================
        # Determine digest period
        # ========================================

        if options["force"]:

            period = options["period"]


            # --forceだけ指定した場合
            # 現在時刻からperiodを決定
            if not period:

                hour = now_zurich.hour

                if hour < 9:

                    period = "morning"

                elif hour < 14:

                    period = "late_morning"

                elif hour < 19:

                    period = "afternoon"

                else:

                    period = "evening"


            self.stdout.write(
                self.style.WARNING(
                    (
                        "Forced refresh request. "
                        f"Period: {period}"
                    )
                )
            )


        else:

            # 通常のCron実行
            # 06 / 11 / 16 / 21時だけ実行
            period = REFRESH_HOURS.get(
                now_zurich.hour
            )


            if not period:

                self.stdout.write(
                    self.style.WARNING(
                        (
                            "Not a scheduled Zurich "
                            "refresh hour. Skipping."
                        )
                    )
                )

                return


            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Scheduled refresh. "
                        f"Period: {period}"
                    )
                )
            )


        # ========================================
        # Send refresh request to Web Service
        # ========================================

        try:

            response = requests.post(
                refresh_url,

                headers={
                    "X-News-Refresh-Token":
                        refresh_token,
                },

                data={
                    "period": period,
                },

                timeout=30,
            )

            response.raise_for_status()


        except requests.RequestException as exc:

            self.stderr.write(
                self.style.ERROR(
                    (
                        "Refresh request failed: "
                        f"{exc}"
                    )
                )
            )

            raise


        # ========================================
        # Success
        # ========================================

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Refresh request accepted. "
                    f"Period: {period}"
                )
            )
        )


        self.stdout.write(
            response.text
        )