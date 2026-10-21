"""
2026-10-21: 新しい洋食10品を公開する (確認済み)。
すでに下書きで取り込んだ環境のためのもの。まだない環境では、
import_washoku が最初から公開で追加する。
"""

from django.db import migrations


NEW_YOSHOKU = [
    "ナポリタン", "煮込みハンバーグ", "クリームシチュー", "ハヤシライス", "マカロニグラタン",
    "えびドリア", "コロッケ", "ロールキャベツ", "ポークチャップ", "ツナと大根おろしの和風スパゲッティ",
]


def publish(apps, schema_editor):

    Recipe = apps.get_model("washoku", "Recipe")

    (
        Recipe.objects
        .filter(name__in=NEW_YOSHOKU, status="draft")
        .exclude(origin="member")
        .update(status="published")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0012_links_store_labels"),
    ]

    operations = [
        migrations.RunPython(publish, migrations.RunPython.noop),
    ]
