from django.db import migrations


# 2026-10-21: 日本の家庭の洋食を「洋食」カテゴリーにまとめる
YOSHOKU = [
    "和風ハンバーグ",
    "メンチカツ",
    "エビフライ",
    "チキンライス",
    "オムライス",
    "カレーライス",
    "きのこの和風醤油パスタ",
]


def move(apps, schema_editor):

    Recipe = apps.get_model("washoku", "Recipe")

    Recipe.objects.filter(name__in=YOSHOKU).update(category="yoshoku")


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0008_nutrition_yoshoku_posts"),
    ]

    operations = [
        migrations.RunPython(move, migrations.RunPython.noop),
    ]
