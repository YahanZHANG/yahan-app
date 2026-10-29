from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations


ZURICH = ZoneInfo("Europe/Zurich")

EDITOR_USERNAME = "yapp_editor"
EDITOR_NAME = "Yapp編集部"

# (どこに, 名前, 本文, 日時)。レシピ・食材のページにはコメント、ページのない話題は短いコラムにする
TIPS = [
    ("recipe", "鶏の唐揚げ", "片栗粉がない場合は、Kartoffelstärke（じゃがいもでんぷん）も候補に。衣の食感が変わるので、好みに合わせて調整してみてください！", (10, 25, 9, 12)),
    ("recipe", "豚汁", "大根が手に入らない場合は、Kohlrabi（コールラビ）を入れてみるのも面白そう。甘みのある野菜なので、味噌との相性もよさそうです。", (10, 25, 19, 47)),
    ("column", "Quarkは日本のヨーグルト？", "スイスでよく見かけるQuarkは、ヨーグルトではなくフレッシュチーズの一種。プレーンタイプは料理やデザートにも活用できます！", (10, 26, 7, 38)),
    ("recipe", "お好み焼き", "キャベツの代わりに、スイスのWeisskabisを使う方法も。葉が硬めの場合は、細かく刻むと生地になじみやすくなります。", (10, 26, 12, 21)),
    ("ingredient", "パン粉", "普通の細かいパン粉はPaniermehl、日本風の粗いパン粉はPankoという名前で探してみてください。揚げ物の食感が結構変わります！", (10, 26, 18, 5)),
    ("recipe", "すき焼き", "白菜や長ねぎが手に入らない場合は、Lauch（ポロねぎ）を使うアレンジも。甘辛い割り下とよく合います。", (10, 26, 21, 33)),
    ("column", "Crème fraîcheは料理に便利", "スイスのスーパーでよく見かけるCrème fraîche。クリーム系パスタやソース、グラタンなどに使いやすい乳製品です。", (10, 27, 8, 16)),
    ("ingredient", "片栗粉", "レシピに登場するSpeisestärkeは、でんぷんの総称。トウモロコシ由来やじゃがいも由来などがあるので、片栗粉の代用には原材料もチェックしてみてください。", (10, 27, 13, 2)),
    ("recipe", "ポテトサラダ", "スイスのじゃがいもで作るポテトサラダもおすすめ。形を残したいならfestkochend、なめらかに潰したいならmehligkochendが候補です。", (10, 27, 17, 44)),
    ("ingredient", "みりん", "アジアスーパーでみりんを買うときは、商品名だけでなく原材料もチェック！本みりんとみりん風調味料では、アルコール分や味わいが異なります。", (10, 27, 20, 58)),
    ("column", "Nüsslisalatって何？", "スイスでよく見かけるNüsslisalatは、柔らかい葉のサラダ野菜。和風ドレッシングやごま和え風の味付けにも合いそうです。", (10, 28, 10, 27)),
    ("ingredient", "黒ごぼう", "Schwarzwurzelは見た目がゴボウに似ていますが、別の植物。きんぴら風に調理することもできますが、日本のゴボウとは味や食感が異なります。", (10, 28, 16, 9)),
]


def add_editor_tips(apps, schema_editor):
    """
    「Yapp編集部」の名前で、レシピ・食材へのひとことと短いコラムを載せる。
    レシピがまだない空の DB (テストなど) では何もしない。同じ文がもうあれば足さない。
    """

    Recipe = apps.get_model("washoku", "Recipe")
    Ingredient = apps.get_model("washoku", "Ingredient")
    Comment = apps.get_model("washoku", "Comment")
    Post = apps.get_model("washoku", "Post")
    User = apps.get_model(settings.AUTH_USER_MODEL)
    UserProfile = apps.get_model("core", "UserProfile")

    if not Recipe.objects.exists():
        return

    editor, created = User.objects.get_or_create(
        username=EDITOR_USERNAME,
        defaults={"is_staff": True, "is_active": True, "password": "!"},
    )
    profile, _ = UserProfile.objects.get_or_create(user=editor)
    if not profile.nickname:
        profile.nickname = EDITOR_NAME
        profile.nickname_setup_completed = True
        profile.save()

    for where, name, body, (month, day, hour, minute) in TIPS:

        at = datetime(2026, month, day, hour, minute, tzinfo=ZURICH)

        if where == "column":
            if Post.objects.filter(title=name).exists():
                continue
            post = Post.objects.create(kind="column", title=name, body=body, author=editor, status="published")
            Post.objects.filter(pk=post.pk).update(created_at=at)
            continue

        target = (Recipe if where == "recipe" else Ingredient).objects.filter(name=name).first()

        if target is None or Comment.objects.filter(body=body).exists():
            continue

        comment = Comment.objects.create(author=editor, kind="tip", body=body, admin_checked=True, **{where: target})
        Comment.objects.filter(pk=comment.pk).update(created_at=at)


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0051_store_comments_to_reviews"),
        ("core", "0027_userprofile_theme_preference"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(add_editor_tips, migrations.RunPython.noop),
    ]
