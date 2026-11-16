"""2026-11-16 Taro: 掲示板を一般公開する (マージした時点で、だれでも見られるように)"""

from django.db import migrations
from django.utils import timezone


def open_board(apps, schema_editor):
    BoardSettings = apps.get_model("chiebukuro", "BoardSettings")
    row, _ = BoardSettings.objects.get_or_create(pk=1)
    row.is_open = True
    if not row.release_start:
        row.release_start = timezone.localdate()
    row.save()


class Migration(migrations.Migration):
    dependencies = [("chiebukuro", "0032_best_answer")]
    operations = [migrations.RunPython(open_board, migrations.RunPython.noop)]
