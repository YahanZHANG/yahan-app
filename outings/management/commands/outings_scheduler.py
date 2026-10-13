
"""
Run the Outings daily update inside the Render Web Service.

- Runs once per UTC day at approximately 05:00.
- Uses a persistent lock and daily attempt marker.
- Does not retry automatically after an interrupted run.
- Linux/Render only (uses fcntl).
"""

import fcntl
import os
import time
import traceback

from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


RUN_HOUR_UTC = 5
RUN_WINDOW_MINUTES = 10
CHECK_INTERVAL_SECONDS = 30


class Command(BaseCommand):

    help = "Run the daily Outings update automatically on Render."

    def handle(self, *args, **options):

        db_path = Path(settings.DATABASES["default"]["NAME"])
        state_dir = db_path.parent / "outings_scheduler"
        state_dir.mkdir(parents=True, exist_ok=True)

        lock_path = state_dir / "scheduler.lock"

        self.stdout.write(
            f"Outings scheduler started. "
            f"UTC run hour={RUN_HOUR_UTC:02d}:00"
        )

        with open(lock_path, "a+", encoding="utf-8") as lock_file:

            try:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            except BlockingIOError:
                self.stdout.write(
                    "Another Outings scheduler is running. Exiting."
                )
                return

            while True:

                now = datetime.now(timezone.utc)

                in_run_window = (
                    now.hour == RUN_HOUR_UTC
                    and now.minute < RUN_WINDOW_MINUTES
                )

                if in_run_window:

                    day = now.strftime("%Y-%m-%d")

                    attempt_path = state_dir / f"{day}.attempted"
                    success_path = state_dir / f"{day}.success"

                    if not attempt_path.exists():

                        # Atomic marker: never start the same
                        # day's job twice, including after restarts.
                        try:
                            fd = os.open(
                                str(attempt_path),
                                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                                0o600,
                            )
                        except FileExistsError:
                            fd = None

                        if fd is not None:

                            with os.fdopen(fd, "w") as file:
                                file.write(
                                    f"Started: {now.isoformat()}\n"
                                )

                            self.stdout.write(
                                f"Starting daily Outings update: {day}"
                            )

                            try:

                                call_command(
                                    "daily_outings",
                                    commit=True,
                                    max_new=15,
                                    max_ai=40,
                                    pages=30,
                                    days=30,
                                    cleanup=True,
                                    images=True,
                                )

                                success_path.write_text(
                                    datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                    encoding="utf-8",
                                )

                                self.stdout.write(
                                    f"Daily Outings update completed: {day}"
                                )

                            except Exception:

                                self.stderr.write(
                                    f"Daily Outings update FAILED: {day}"
                                )
                                self.stderr.write(
                                    traceback.format_exc()
                                )

                                # Deliberately do not retry automatically.
                                # Some events may already have been saved.
                                # Inspect logs before retrying.

                time.sleep(CHECK_INTERVAL_SECONDS)
