from django.db import migrations, models


STAMPS = [
    ("like", "👍", "いいね"),
    ("thanks", "🙏", "ありがとう"),
    ("helped", "🥹", "助かった"),
    ("insight", "💡", "なるほど"),
    ("learned", "📚", "勉強になる"),
    ("surprise", "😲", "意外！"),
    ("metoo", "🙋", "私も知りたかった"),
    ("relate", "🤝", "わかる〜"),
    ("empathy", "🫶", "共感"),
    ("yummy", "😋", "おいしそう"),
    ("tasty", "🍚", "おいしかった"),
    ("cook", "🍳", "作ってみる"),
    ("buy", "🛒", "買ってみる"),
    ("lovely", "✨", "ステキ"),
    ("genius", "🤩", "天才"),
    ("lol", "😂", "笑った"),
    ("cheer", "💪", "がんばる"),
    ("congrats", "🎉", "おめでとう"),
    ("check", "👀", "確認します"),
]


def seed_stamps(apps, schema_editor):
    Stamp = apps.get_model("washoku", "Stamp")

    for order, (key, emoji, label) in enumerate(STAMPS, start=1):
        Stamp.objects.get_or_create(
            key=key,
            defaults={"emoji": emoji, "label": label, "order": order * 10},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0030_featured_pick_reopen"),
    ]

    operations = [
        migrations.CreateModel(
            name="Stamp",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=20, unique=True, verbose_name="ID（英字・あとから変えない）")),
                ("emoji", models.CharField(max_length=16, verbose_name="絵文字")),
                ("label", models.CharField(max_length=20, verbose_name="言葉")),
                ("order", models.PositiveSmallIntegerField(default=100, verbose_name="並び順")),
                ("is_active", models.BooleanField(default=True, help_text="外すと選べなくなります（押されたぶんは残ります）", verbose_name="表示する")),
            ],
            options={
                "verbose_name": "スタンプ",
                "verbose_name_plural": "スタンプ",
                "ordering": ["order", "pk"],
            },
        ),
        migrations.AlterField(
            model_name="commentreaction",
            name="kind",
            field=models.CharField(max_length=20, verbose_name="種類"),
        ),
        migrations.AlterField(
            model_name="postreaction",
            name="kind",
            field=models.CharField(max_length=20, verbose_name="種類"),
        ),
        migrations.AlterField(
            model_name="notification",
            name="stamp",
            field=models.CharField(blank=True, max_length=20, verbose_name="スタンプ"),
        ),
        migrations.RunPython(seed_stamps, migrations.RunPython.noop),
    ]
