"""
先行テスト用に、架空の「募集・告知」を入れる (is_sample=True、「テスト用・架空」の印つき)。
出した人は最初の管理者 (問い合わせは運営に届く)。管理者がいない DB では何もしない。
公開前に、管理画面「募集・告知」の操作「テスト用（架空）の告知をすべて消す」で消す。
"""

from datetime import timedelta

from django.conf import settings
from django.db import migrations
from django.utils import timezone


# (種類, タイトル, 内容, 地域, 場所, 何日後のイベントか or None, ニックネーム)
SAMPLES = [
    ("shop", "日本のお弁当、週末だけ予約販売しています",
     "唐揚げ弁当・鮭弁当など、日本の家庭の味のお弁当を作っています。土曜日の受け取りで、前の週の水曜日までに予約をお願いします。アレルギーのある方は、問い合わせでご相談ください。",
     "zurich", "チューリッヒ市内（受け取り場所はご相談）", None, "おむすび食堂"),
    ("shop", "日本語でできる、まつげパーマ・ネイルのサロンです",
     "自宅の一角で、まつげパーマとジェルネイルをしています。日本語で、ゆっくりご相談いただけます。平日の昼間と土曜日が空いています。",
     "basel", "バーゼル駅から徒歩10分", None, "サロン・ゆき"),
    ("lesson", "子ども向け 日本語の読み聞かせと工作の会",
     "4〜7歳のお子さん向けに、日本語の絵本の読み聞かせと、簡単な工作をしています。月2回、土曜日の午前中です。体験参加もできます。",
     "zurich", "チューリッヒ・エアリコン", None, "えほんの会"),
    ("lesson", "大人のためのドイツ語会話、少人数で練習しませんか",
     "日本人向けのドイツ語会話の練習会です。病院・役所・学校の先生との会話など、生活でよく使う場面を練習します。A2くらいの方が中心です。",
     "bern", "ベルン旧市街のカフェ", None, "ドイツ語れんしゅう会"),
    ("event", "秋のおにぎり持ちよりピクニック",
     "子連れも大人だけも歓迎の、ゆるいピクニックです。おにぎりを1人1つ持ってきて、交換しながら食べましょう。雨の日は中止です。",
     "zurich", "チューリッヒ湖のほとり（集合場所は問い合わせで）", 9, "ピクニック係"),
    ("event", "日本の古本・絵本の交換会",
     "読み終わった日本語の本や絵本を持ちよって、交換する会です。お金のやりとりはありません。本がなくても、見に来るだけで大丈夫です。",
     "lucerne", "ルツェルン駅の近くの集会室", 16, "本の交換会"),
    ("friends", "週末にハイキングする仲間を探しています",
     "月1〜2回、初心者向けのコースを歩いています。30〜40代が多いですが、年齢は問いません。ゆっくりペースなので、体力に自信がない方もどうぞ。",
     "zug", "ツーク周辺の山", None, "やまある記"),
    ("friends", "ジュネーブ近くの日本人ママ、お茶しませんか",
     "0〜3歳の子どもがいるママで、月1回、カフェでおしゃべりしています。フランス語圏の子育ての情報交換もできます。",
     "geneva", "ジュネーブ市内のカフェ", None, "レマン湖ママ会"),
    ("sitter_find", "平日の夕方、子ども（6歳）を見てくださる方を探しています",
     "週2回、17〜19時に、小学1年生の子どもを見てくださる方を探しています。お迎えと、家で宿題を見ていただくお願いです。日本語で話せる方を希望します。",
     "winterthur", "ヴィンタートゥール", None, "はるママ"),
    ("sitter_offer", "週末のベビーシッター、お手伝いできます",
     "日本で保育士をしていました。土日の日中、お子さんを見るお手伝いができます。まずは、ご家族と一緒に一度お会いしてからお受けしています。",
     "zurich", "チューリッヒ市内", None, "保育士のあや"),
    ("other", "日本への一時帰国、荷物の受け渡しを手伝ってほしい方",
     "12月に一時帰国します。日本で受け取りたい手紙や小さなもの（書類など）があれば、お預かりできます。食べもの・医薬品はお受けできません。",
     "basel", "バーゼル", None, "帰国組のたける"),
]


def forwards(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Notice = apps.get_model("chiebukuro", "Notice")
    owner = (User.objects.filter(is_superuser=True).order_by("pk").first()
             or User.objects.filter(is_staff=True).order_by("pk").first())
    if owner is None or Notice.objects.filter(is_sample=True).exists():
        return
    now = timezone.now()
    for minutes, (kind, title, body, region, place, days, nickname) in enumerate(SAMPLES):
        Notice.objects.create(
            kind=kind,
            title=title,
            body=body,
            region=region,
            place=place,
            event_date=(now + timedelta(days=days)).date() if days else None,
            owner=owner,
            nickname=nickname,
            is_sample=True,
            expires_at=now + timedelta(days=30),
            created_at=now - timedelta(hours=minutes * 5),
        )


def backwards(apps, schema_editor):
    apps.get_model("chiebukuro", "Notice").objects.filter(is_sample=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0014_notice_is_sample"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
