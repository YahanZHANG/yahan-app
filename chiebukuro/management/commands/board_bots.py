"""
つぶやきBotの予約。

  python manage.py board_bots                       予約の一覧 (これから出るもの)
  python manage.py board_bots --release             時間になった予約を今すぐ出す
  python manage.py board_bots --schedule 2026-12-12 --days 30
                                                    その日から N 日分の予約を足す (あるものはそのまま)
  python manage.py board_bots --preview washoku     自動で作る Bot の中身を試しに作って表示 (投稿しない)
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from chiebukuro import bots
from chiebukuro.models import BotPost


class Command(BaseCommand):
    help = "つぶやきBotの予約の一覧・追加・投稿"

    def add_arguments(self, parser):
        parser.add_argument("--release", action="store_true")
        parser.add_argument("--schedule", metavar="YYYY-MM-DD")
        parser.add_argument("--days", type=int, default=bots.TRIAL_DAYS)
        parser.add_argument("--preview", choices=sorted(bots.BUILDERS))

    def handle(self, *args, **options):
        if options["schedule"]:
            made = bots.schedule(BotPost, date.fromisoformat(options["schedule"]), options["days"])
            self.stdout.write(f"{made}件の予約を足しました。")
        if options["release"]:
            self.stdout.write(f"{bots.release_due()}件を投稿しました。")
        if options["preview"]:
            now = timezone.now()
            slot = BotPost(bot=options["preview"], publish_at=now)
            content = bots.BUILDERS[options["preview"]](slot, now)
            if not content:
                self.stdout.write("出せるデータがありません。")
                return
            self.stdout.write(f"{content.get('tag', '')}\n{content.get('title', '')}\n\n{content['body']}")
            for link in content.get("links", []):
                self.stdout.write(f"→ {link['label']}  {link['url']}")
            return
        if not (options["schedule"] or options["release"]):
            for slot in BotPost.objects.filter(state=BotPost.State.WAITING).order_by("publish_at")[:40]:
                when = timezone.localtime(slot.publish_at)
                self.stdout.write(f"{when:%m/%d %H:%M}  {slot.get_bot_display():<12} {slot.title or slot.body[:30] or '（自動）'}")
