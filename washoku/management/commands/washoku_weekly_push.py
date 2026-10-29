from django.core.management.base import BaseCommand

from washoku.weekly_push import send_weekly_push, weekly_message


class Command(BaseCommand):

    help = "毎週月曜の「今週」のお知らせを、いますぐ送る (--dry-run なら文面を見るだけ)。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="送らずに文面だけ表示する")

    def handle(self, *args, **options):

        message = weekly_message()

        if message is None:
            self.stdout.write("今週は知らせることがありません (アンケートも、編集部のひとこともありません)。")
            return

        title, body = message
        self.stdout.write(f"タイトル: {title}\n本文: {body}")

        if options["dry_run"]:
            return

        self.stdout.write(f"{send_weekly_push()} 台に送りました。")
