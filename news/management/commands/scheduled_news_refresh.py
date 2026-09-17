import os
from zoneinfo import ZoneInfo

import requests

from django.core.management.base import BaseCommand
from django.utils import timezone


ZURICH_TZ = ZoneInfo(
    "Europe/Zurich"
)


class Command(BaseCommand):
    help = (
        "Ask the Yahan-app web service to refresh "
        "Swiss news at 06:00 or 15:00 Zurich time."
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
                "afternoon",
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
        # Determine period
        # ========================================

        if options["force"]:

            period = options["period"]

            if not period:
                period = (
                    "morning"
                    if now_zurich.hour < 12
                    else "afternoon"
                )

            self.stdout.write(
                self.style.WARNING(
                    (
                        "Forced refresh request. "
                        f"Period: {period}"
                    )
                )
            )


        elif now_zurich.hour == 6:

            period = "morning"


        elif now_zurich.hour == 15:

            period = "afternoon"


        else:

            self.stdout.write(
                self.style.WARNING(
                    (
                        "Not a scheduled Zurich "
                        "refresh hour. Skipping."
                    )
                )
            )

            return


        # ========================================
        # Send request to Web Service
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