"""
2026-11-16 Taro: 事前アンケートのゆずりあいの希望から作った品物を消す (書いた人が掲示板を見るとは限らないので)。
取り込みの記録 (SurveyImport) は残すので、また出てくることはない。
"""

from django.db import migrations

SURVEY_BODY = "事前アンケートで寄せられた希望です。"


def remove(apps, schema_editor):
    Item = apps.get_model("chiebukuro", "Item")
    Item.objects.filter(body=SURVEY_BODY).delete()


class Migration(migrations.Migration):
    dependencies = [("chiebukuro", "0033_open_board")]
    operations = [migrations.RunPython(remove, migrations.RunPython.noop)]
