"""
Run the Outings daily update inside the Render Web Service.

- First attempt at RUN_HOUR_UTC (01:00 UTC = 02:00/03:00 in Zurich).
- If it fails, retries up to MAX_ATTEMPTS per UTC day, RETRY_MINUTES apart.
  A rerun is safe: AI results are cached and imported events are skipped.
- A deploy or restart during the night no longer skips the day: the job runs
  as soon as the scheduler is up and the day has no success yet.
- Each failure is emailed to ADMIN_NOTIFICATION_EMAIL.
- The update runs in a child process, so the memory it uses (Eventfrog
  pages, AI replies) is given back when it ends instead of staying in this
  long-lived process.
- The same loop also sends the スイスで和食 weekly push (Mondays 16:00
  Zurich), so no extra process is needed.
- Linux/Render only (uses fcntl).
"""

import fcntl
import subprocess
import sys
import time

from collections import deque

from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from outings.services.alerts import send_admin_alert
from washoku.weekly_push import run_if_due as run_washoku_weekly_push


RUN_HOUR_UTC = 1
MAX_ATTEMPTS = 3
RETRY_MINUTES = 90
CHECK_INTERVAL_SECONDS = 60
KEEP_MARKERS_DAYS = 30

DAILY_OPTIONS = dict(
    commit=True,
    max_new=15,
    max_screen=500,
    pages=30,
    days=30,
    cleanup=True,
    images=True,
)


def daily_command():
    command = [sys.executable, "-u", str(Path(settings.BASE_DIR) / "manage.py"), "daily_outings"]
    for name, value in DAILY_OPTIONS.items():
        flag = "--" + name.replace("_", "-")
        if value is True:
            command.append(flag)
        else:
            command += [flag, str(value)]
    return command


def run_daily(write):
    """Run daily_outings in a child process. Returns (ok, last output lines)."""
    tail = deque(maxlen=60)
    with subprocess.Popen(
        daily_command(), cwd=settings.BASE_DIR, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    ) as process:
        for line in process.stdout:
            line = line.rstrip("\n")
            write(line)
            tail.append(line)
    return process.returncode == 0, "\n".join(tail)


def attempts(state_dir, day):
    return sorted(state_dir.glob(f"{day}.attempt-*"))


def next_attempt(state_dir, now):
    """Return the attempt number to start now, or None."""
    if now.hour < RUN_HOUR_UTC:
        return None
    day = now.strftime("%Y-%m-%d")
    if (state_dir / f"{day}.success").exists():
        return None
    done = attempts(state_dir, day)
    if len(done) >= MAX_ATTEMPTS:
        return None
    if done:
        last = datetime.fromtimestamp(done[-1].stat().st_mtime, tz=timezone.utc)
        if now - last < timedelta(minutes=RETRY_MINUTES):
            return None
    return len(done) + 1


def prune(state_dir, now):
    cutoff = (now - timedelta(days=KEEP_MARKERS_DAYS)).strftime("%Y-%m-%d")
    for path in state_dir.iterdir():
        if path.name[:10] < cutoff and path.name[:4].isdigit():
            path.unlink(missing_ok=True)


class Command(BaseCommand):

    help = "Run the daily Outings update automatically on Render."

    def handle(self, *args, **options):

        db_path = Path(settings.DATABASES["default"]["NAME"])
        state_dir = db_path.parent / "outings_scheduler"
        state_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(
            f"Outings scheduler started. UTC run hour={RUN_HOUR_UTC:02d}:00, "
            f"up to {MAX_ATTEMPTS} attempts per day"
        )

        with open(state_dir / "scheduler.lock", "a+", encoding="utf-8") as lock_file:

            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.stdout.write("Another Outings scheduler is running. Exiting.")
                return

            while True:
                now = datetime.now(timezone.utc)
                attempt = next_attempt(state_dir, now)
                if attempt is not None:
                    self.run(state_dir, now, attempt)
                    prune(state_dir, now)
                self.washoku_weekly_push(db_path.parent / "washoku_scheduler")
                time.sleep(CHECK_INTERVAL_SECONDS)

    def washoku_weekly_push(self, state_dir):
        # 和食の通知が失敗しても、Outings の更新は止めない
        try:
            run_washoku_weekly_push(state_dir, write=self.stdout.write)
        except Exception as exc:
            self.stderr.write(f"Washoku weekly push FAILED: {type(exc).__name__}: {exc}")

    def run(self, state_dir, now, attempt):
        day = now.strftime("%Y-%m-%d")
        (state_dir / f"{day}.attempt-{attempt}").write_text(f"Started: {now.isoformat()}\n", encoding="utf-8")
        self.stdout.write(f"Starting daily Outings update: {day} (attempt {attempt}/{MAX_ATTEMPTS})")
        try:
            ok, details = run_daily(self.stdout.write)
        except OSError as exc:
            ok, details = False, f"{type(exc).__name__}: {exc}"
        if not ok:
            self.stderr.write(f"Daily Outings update FAILED: {day} (attempt {attempt})")
            self.stderr.write(details)
            if attempt < MAX_ATTEMPTS:
                note = f"{RETRY_MINUTES}分後に自動で再実行します（{attempt}/{MAX_ATTEMPTS}回目）。"
            else:
                note = "今日の自動再実行はこれで終わりです。Render のログを確認してください。"
            send_admin_alert(
                f"毎日の更新に失敗しました（{day}）",
                f"{note}\n\n{details[-3000:]}",
            )
            return
        (state_dir / f"{day}.success").write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        self.stdout.write(f"Daily Outings update completed: {day}")
