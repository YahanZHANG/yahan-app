from django.conf import settings
from django.db import migrations
from django.utils import timezone


FIRST_POLLS = [
    {
        "title": "ぶっちゃけ、スイスで生卵を食べたことある？",
        "body": "卵かけご飯、すき焼きのつけ卵など。",
        "ingredient": "卵",
        "choices": ["ある", "ない"],
    },
    {
        "title": "じゃがいもは、いつも何色の袋を買っている？",
        "body": "",
        "ingredient": "じゃがいも",
        "choices": ["緑", "赤", "青", "その他", "わからない・色を気にしたことがない"],
    },
]


def add_first_polls(apps, schema_editor):
    """
    最初のアンケート2つ。管理画面で消したら、もう戻らない。
    """

    Post = apps.get_model("washoku", "Post")
    PollChoice = apps.get_model("washoku", "PollChoice")
    Ingredient = apps.get_model("washoku", "Ingredient")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    # 食材がまだない空のデータベース (テストなど) には入れない
    if not Ingredient.objects.exists():
        return

    owner = User.objects.filter(is_superuser=True).order_by("pk").first()
    now = timezone.now()

    for index, poll in enumerate(FIRST_POLLS):

        post = Post.objects.create(
            kind="poll",
            title=poll["title"],
            body=poll["body"],
            author=owner,
            status="published",
            created_at=now - timezone.timedelta(minutes=len(FIRST_POLLS) - index),
        )

        for order, label in enumerate(poll["choices"]):
            PollChoice.objects.create(post=post, label=label, order=order)

        post.ingredients.set(Ingredient.objects.filter(name=poll["ingredient"]))


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0027_polls"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(add_first_polls, migrations.RunPython.noop),
    ]
