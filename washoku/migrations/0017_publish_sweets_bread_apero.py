"""
2026-10-21: デザート・パン・アペロの15品を公開する (確認済み)。
すでに下書きで取り込んだ環境のためのもの。まだない環境では、
import_washoku が最初から公開で追加する。
"""

from django.db import migrations


NEW_RECIPES = [
    "ふわふわホットケーキ", "ガトーショコラ", "カスタードプリン", "大学芋", "ふわふわ蒸しパン",
    "食パン", "メロンパン", "クリームパン", "たまごサンド", "ハムサンド",
    "肉味噌クラッカー", "野菜スティックと味噌マヨディップ", "ハムのクロワッサン（Schinkengipfeli）",
    "焼き鳥風ピック", "枝豆のガーリック炒め",
]


def publish(apps, schema_editor):

    Recipe = apps.get_model("washoku", "Recipe")

    (
        Recipe.objects
        .filter(name__in=NEW_RECIPES, status="draft")
        .exclude(origin="member")
        .update(status="published")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0016_stamps"),
    ]

    operations = [
        migrations.RunPython(publish, migrations.RunPython.noop),
    ]
