from django.core.management.base import BaseCommand

from chiebukuro.services import import_from_survey


class Command(BaseCommand):
    help = "事前アンケートの質問と、公開に同意した答えを掲示板に取り込む (取り込み済みは飛ばす)"

    def handle(self, *args, **options):
        questions, answers = import_from_survey()
        self.stdout.write(f"知恵袋: 質問 {questions} 件、答え {answers} 件を取り込みました")
