"""最初のアンケートを3つ入れる (まだ1つもなく、利用者がいる DB だけ。テスト用の空の DB には入れない)"""

from django.conf import settings
from django.db import migrations


POLLS = [
    ("スイスに住んで何年目？", ["1年未満", "1〜3年", "4〜10年", "10年以上"]),
    ("日本の食材、どこで買うことが多い？", ["アジア食材店", "Coop・Migros", "ネット通販", "日本から持ってくる"]),
    ("スイスの冬、いちばんつらいのは？", ["日が短い・暗い", "寒さ", "乾燥", "お店が早く閉まる"]),
]


def add_polls(apps, schema_editor):
    Poll = apps.get_model("chiebukuro", "Poll")
    PollChoice = apps.get_model("chiebukuro", "PollChoice")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    if Poll.objects.exists() or not User.objects.exists():
        return
    for question, labels in POLLS:
        poll = Poll.objects.create(question=question)
        for order, label in enumerate(labels):
            PollChoice.objects.create(poll=poll, label=label, order=order)


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0005_profile_face_home_pick"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(add_polls, migrations.RunPython.noop)]
