from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


ZURICH_TZ = ZoneInfo(
    "Europe/Zurich"
)


class Command(BaseCommand):
    help = (
        "Run the Swiss news refresh at "
        "06:00 or 15:00 Europe/Zurich time."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Run immediately regardless "
                "of the current Zurich time."
            ),
        )


    def handle(
        self,
        *args,
        **options,
    ):

        now_utc = timezone.now()

        now_zurich = (
            now_utc
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


        # -------------------------
        # Manual test
        # -------------------------

        if options["force"]:

            period = (
                "morning"
                if now_zurich.hour < 12
                else "afternoon"
            )

            self.stdout.write(
                self.style.WARNING(
                    (
                        "Forced refresh. "
                        f"Period: {period}"
                    )
                )
            )

            call_command(
                "refresh_news",
                period=period,
            )

            return


        # -------------------------
        # Morning
        # -------------------------

        if now_zurich.hour == 6:

            self.stdout.write(
                self.style.SUCCESS(
                    "Starting morning refresh."
                )
            )

            call_command(
                "refresh_news",
                period="morning",
            )

            return


        # -------------------------
        # Afternoon
        # -------------------------

        if now_zurich.hour == 15:

            self.stdout.write(
                self.style.SUCCESS(
                    "Starting afternoon refresh."
                )
            )

            call_command(
                "refresh_news",
                period="afternoon",
            )

            return


        # -------------------------
        # DST helper run
        # -------------------------

        self.stdout.write(
            self.style.WARNING(
                (
                    "Not a scheduled Zurich "
                    "refresh hour. Skipping."
                )
            )
        )