import os
import time
from pathlib import Path

from django.core.management import (
    call_command,
)
from django.core.management.base import (
    BaseCommand,
)


LOCK_PATH = Path(
    os.environ.get(
        "NEWS_REFRESH_LOCK_PATH",
        "/var/data/news_refresh.lock",
    )
)

STALE_LOCK_SECONDS = (
    2 * 60 * 60
)


class Command(BaseCommand):
    help = (
        "Run news refresh with a lock "
        "to prevent overlapping jobs."
    )


    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--period",
            choices=[
                "morning",
                "late_morning",
                "afternoon",
                "evening",
            ],
            required=True,
        )


    def handle(
        self,
        *args,
        **options,
    ):
        period = options["period"]

        # -------------------------
        # Remove stale lock
        # -------------------------

        if LOCK_PATH.exists():

            age = (
                time.time()
                - LOCK_PATH.stat().st_mtime
            )

            if age > STALE_LOCK_SECONDS:

                self.stdout.write(
                    self.style.WARNING(
                        "Removing stale refresh lock."
                    )
                )

                LOCK_PATH.unlink(
                    missing_ok=True
                )


        # -------------------------
        # Acquire lock
        # -------------------------

        try:

            fd = os.open(
                LOCK_PATH,
                os.O_CREAT
                | os.O_EXCL
                | os.O_WRONLY,
            )

            os.write(
                fd,
                str(
                    os.getpid()
                ).encode(),
            )

            os.close(fd)

        except FileExistsError:

            self.stdout.write(
                self.style.WARNING(
                    (
                        "Another news refresh "
                        "is already running. "
                        "Skipping."
                    )
                )
            )

            return


        try:

            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Starting news refresh. "
                        f"Period: {period}"
                    )
                )
            )

            call_command(
                "refresh_news",
                period=period,
            )

        finally:

            LOCK_PATH.unlink(
                missing_ok=True
            )


        self.stdout.write(
            self.style.SUCCESS(
                "News refresh completed."
            )
        )