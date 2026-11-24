from django.db import migrations


def schedule_more(apps, schema_editor):
    # スイスを知ろうBot Day 31〜60 (Taro, 2026-11-24)。Day 31 = 2026-12-12 8:00
    from chiebukuro.bots import TRIAL_START, schedule

    schedule(apps.get_model("chiebukuro", "BotPost"), TRIAL_START, days=60, first=31)


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0038_answer_unsure"),
    ]

    operations = [
        migrations.RunPython(schedule_more, migrations.RunPython.noop),
    ]
