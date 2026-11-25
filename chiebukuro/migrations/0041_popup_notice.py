"""お知らせのポップアップ (2026-11-24 Taro)。最初のお知らせ: アンケートと「知らんけど」"""

from django.db import migrations, models
import django.utils.timezone


BODY = """📊 アンケートができました
気軽に答えて、みんなの結果を見てみてください。だれでもアンケートを作れます。

🤷 自信がない回答には「知らんけど」
回答するときに「知らんけど」ボタンを押すと、自信がないことが伝わります。気軽に答えてみてください。"""


def add_first(apps, schema_editor):
    PopupNotice = apps.get_model("chiebukuro", "PopupNotice")
    if not PopupNotice.objects.exists():
        PopupNotice.objects.create(
            title="新しい機能のお知らせ",
            body=BODY,
            link_url="/swiss-board/polls/",
            link_label="アンケートを見る",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0040_merge_polls_bot"),
    ]

    operations = [
        migrations.CreateModel(
            name="PopupNotice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=60, verbose_name="タイトル")),
                ("body", models.TextField(help_text="空行で区切ると段落になり、各段落の1行目が太字の見出しになります。", verbose_name="本文")),
                ("link_url", models.CharField(blank=True, help_text="例: /swiss-board/polls/ (空ならボタンなし)", max_length=300, verbose_name="ボタンのリンク先")),
                ("link_label", models.CharField(blank=True, max_length=30, verbose_name="ボタンの文字")),
                ("is_active", models.BooleanField(default=True, verbose_name="出す")),
                ("show_until", models.DateTimeField(blank=True, help_text="空なら、ずっと (はじめて来た人にも出ます)", null=True, verbose_name="いつまで出すか")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="作成日時")),
            ],
            options={"verbose_name": "お知らせポップアップ", "verbose_name_plural": "お知らせポップアップ", "ordering": ["-created_at", "-pk"]},
        ),
        migrations.RunPython(add_first, migrations.RunPython.noop),
    ]
