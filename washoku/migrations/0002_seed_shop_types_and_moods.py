from django.db import migrations


SHOP_TYPES = [
    ("supermarket", "普通のスーパー", "Migros・Coop・Denner・Aldi・Lidl など", 1),
    ("asian", "アジア・中華スーパー", "アジア食材店・中華食材店", 2),
    ("japanese", "日系の店", "日本食材の専門店", 3),
    ("online", "ネット通販", "スイス国内に届く日本食材の通販", 4),
]

MOOD_TAGS = [
    "和の定番が恋しい",
    "さっぱり",
    "がっつり",
    "あったまりたい",
    "野菜たっぷり",
    "ピリ辛",
    "子どもが喜ぶ",
    "お弁当向き",
    "作りおき",
    "おもてなし",
]


def seed(apps, schema_editor):

    ShopType = apps.get_model("washoku", "ShopType")
    MoodTag = apps.get_model("washoku", "MoodTag")

    for code, name, description, rank in SHOP_TYPES:
        ShopType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "rank": rank,
            },
        )

    for order, name in enumerate(MOOD_TAGS, start=1):
        MoodTag.objects.update_or_create(
            name=name,
            defaults={
                "display_order": order * 10,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed,
            migrations.RunPython.noop,
        ),
    ]
