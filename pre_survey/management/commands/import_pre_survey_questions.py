"""
運営の質問を JSON から取り込む。

    python manage.py import_pre_survey_questions [path]

JSON は [{"key": "...", "theme": "life", "body": "...", "region": ""}, ...]。
key ごとに1回だけ取り込む (すでにある key は飛ばす) ので、何度実行してもよい。
管理画面で直した質問が JSON で上書きされることはない。
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from pre_survey.models import REGION_CHOICES, Question, Theme


DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "questions.json"


class Command(BaseCommand):

    help = "事前アンケートの運営の質問を JSON から取り込む (新しいものだけ)"

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default=str(DEFAULT_PATH))

    def handle(self, *args, **options):
        path = Path(options["path"])

        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CommandError(f"{path} を読めません: {error}")

        themes = set(Theme.values)
        regions = {key for key, _ in REGION_CHOICES}
        existing = set(Question.objects.exclude(seed_key=None).values_list("seed_key", flat=True))
        created = 0

        for number, row in enumerate(rows, start=1):
            key = str(row.get("key") or "").strip()
            body = str(row.get("body") or "").strip()
            theme = row.get("theme")
            region = row.get("region") or ""

            if not key or not body:
                raise CommandError(f"{number}件目: key と body が必要です")
            if theme not in themes:
                raise CommandError(f"{number}件目 ({key}): テーマ {theme!r} はありません")
            if region and region not in regions:
                raise CommandError(f"{number}件目 ({key}): 地域 {region!r} はありません")
            if key in existing:
                continue

            Question.objects.create(
                seed_key=key,
                body=body,
                theme=theme,
                region=region,
                source=Question.Source.STAFF,
                status=Question.Status.PUBLISHED,
            )
            existing.add(key)
            created += 1

        if options["verbosity"]:
            self.stdout.write(f"事前アンケート: 質問を{created}件追加しました")
