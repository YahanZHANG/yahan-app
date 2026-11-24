"""アンケート (2026-11-24 Taro): 誰でも作れる・公開日時の予約・1週間で締め切り。
これまでのアンケートは作成日時を公開日時にし (もう締め切り)、非表示だったものも出す (2026-11-24 Taro)。運営のアンケート12問を火・金の朝7時 (スイス時間) に1問ずつ予約する
(利用者がいる DB だけ。テスト用の空の DB には入れない)"""

import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


ZURICH = ZoneInfo("Europe/Zurich")

# Taro が選んだ順番 (1 5 9 2 6 10 3 7 11 4 8 12)
POLLS = [
    ("2026-12-01", "日曜日にお店が閉まっているのは？", ["不便", "もう慣れた", "むしろ好き"]),
    ("2026-12-04", "現地語（ドイツ語・フランス語など）、正直どのくらい話せる？", ["日常会話OK", "簡単なやりとりだけ", "ほぼ英語で生活"]),
    ("2026-12-08", "健康保険のフランチャイズ、いくらにしてる？", ["300", "中間（500〜1500）", "2500"]),
    ("2026-12-11", "共同ランドリーのルールで困ったことは？", ["ある", "ない", "ランドリーは自分専用"]),
    ("2026-12-15", "家族との会話は主に何語？", ["日本語", "現地語・英語", "ミックス"]),
    ("2026-12-18", "一時帰国の頻度は？", ["年1回以上", "2〜3年に1回", "ほとんど帰らない"]),
    ("2026-12-22", "冬の暗さ、気分に影響する？", ["かなりある", "少しある", "平気"]),
    ("2026-12-25", "ビズ（頬のあいさつ）、慣れた？", ["慣れた", "まだ苦手", "周りでは誰もしない"]),
    ("2026-12-29", "一時帰国の帰り、スーツケースの日本食は？", ["半分以上", "少し", "ほぼ入れない"]),
    ("2027-01-01", "外食、どれくらいしてる？", ["週1回以上", "月に数回", "ほとんどしない"]),
    ("2027-01-05", "スイス人の友達はいる？", ["何人もいる", "少しいる", "ほとんどいない"]),
    ("2027-01-08", "この先もスイスに住み続ける？", ["ずっと住むつもり", "いつか日本へ帰る", "まだわからない"]),
]


def schedule(apps, schema_editor):
    Poll = apps.get_model("chiebukuro", "Poll")
    PollChoice = apps.get_model("chiebukuro", "PollChoice")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    for poll in Poll.objects.all():
        poll.publish_at = poll.created_at
        poll.is_active = True
        poll.save(update_fields=["publish_at", "is_active"])
    if not User.objects.exists():
        return
    for day, question, labels in POLLS:
        if Poll.objects.filter(question=question).exists():
            continue
        publish_at = datetime.datetime.combine(datetime.date.fromisoformat(day), datetime.time(7, 0), tzinfo=ZURICH)
        poll = Poll.objects.create(question=question, publish_at=publish_at)
        for order, label in enumerate(labels):
            PollChoice.objects.create(poll=poll, label=label, order=order)


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0038_answer_unsure"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(name="poll", options={"ordering": ["-publish_at", "-pk"], "verbose_name": "アンケート", "verbose_name_plural": "アンケート"}),
        migrations.AlterField(model_name="poll", name="is_active", field=models.BooleanField(default=True, help_text="オフにすると、どこにも出ません。", verbose_name="公開する")),
        migrations.AddField(
            model_name="poll",
            name="author",
            field=models.ForeignKey(blank=True, help_text="空なら「運営」", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="chie_polls", to=settings.AUTH_USER_MODEL, verbose_name="作った人"),
        ),
        migrations.AddField(model_name="poll", name="nickname", field=models.CharField(blank=True, max_length=30, verbose_name="ニックネーム")),
        migrations.AddField(model_name="poll", name="is_anonymous", field=models.BooleanField(default=False, verbose_name="匿名")),
        migrations.AddField(
            model_name="poll",
            name="publish_at",
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, help_text="この日時から出ます (予約できます)。1週間後に締め切り。", verbose_name="公開日時"),
        ),
        migrations.RunPython(schedule, migrations.RunPython.noop),
    ]
