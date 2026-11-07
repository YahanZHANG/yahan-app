"""Publish the family spots checked on their official or tourism-office
pages on 2026-11-07 (batch 3: central Switzerland). Only empty fields are
filled, so edits made in admin are kept; price, age and season are
corrected where the first guesses were wrong."""

import datetime

from django.db import migrations

CHECKED = datetime.date(2026, 11, 7)
CORRECTED = {"price", "age_min", "season"}

SPOTS = {
    "Verkehrshaus der Schweiz": dict(
        official_url="https://www.verkehrshaus.ch", address="Lidostrasse 5, 6006 Luzern",
        hours_note="毎日。夏（3月末〜10月）10:00〜18:00、冬 10:00〜17:00",
        price_note="有料（料金は公式サイトで確認）。電車の往復切符とセットで博物館が30%引き",
        parking_note="電車なら Luzern Verkehrshaus 駅のすぐ前（Luzern 駅から約8分）",
    ),
    "Glasi Hergiswil": dict(
        official_url="https://www.glasi.ch", address="Seestrasse 12, 6052 Hergiswil",
        hours_note="月〜金 9:00〜17:00、土 9:00〜16:00（日曜休み、昼休みあり）",
        price_note="博物館 CHF 7、ガラスの迷路 CHF 5（どちらも10歳未満は大人といっしょなら無料）。自分でガラス玉を吹く体験 CHF 20",
        parking_note="レストラン Adler の裏に駐車場。Hergiswil 駅から歩いて3分",
        tips_ja="ガラス職人の仕事を上から見学できます。外には長いすべり台、大きな砂場、湖のそばの水遊び場もあります。",
    ),
    "Natur- und Tierpark Goldau": dict(
        official_url="https://www.tierpark.ch", address="Parkstrasse 42, 6410 Goldau",
        hours_note="毎日。4〜10月 9:00〜18:00、11〜3月 9:00〜17:00",
        price_note="大人 CHF 25、4〜15歳 CHF 12、3歳以下無料、家族 CHF 67",
        food_note="レストラン Grüne Gans あり", tips_ja="ベビーカーで全部回れます。犬は入れません。",
    ),
    "Rigi": dict(
        official_url="https://www.rigi.ch", address="Rigi Kaltbad, 6356 Rigi Kaltbad",
        hours_note="一年じゅう。電車とロープウェイの時刻は公式サイトで確認",
        price_note="登山鉄道が有料（子どもが無料になる切符もあり。公式サイトで確認）",
        tips_ja="Kaltbad に冒険遊び場 Rigiland、ミニゴルフ。冬はスケートリンクと子ども用スキー場。たき火ができる場所も多いです。",
    ),
    "Seilpark Pilatus Fräkmüntegg": dict(
        official_url="https://www.pilatus.ch", address="Schlossweg 1, 6010 Kriens",
        hours_note="夏のあいだ。強い風や雨の日は閉まります",
        price_note="ロープパーク：大人 CHF 30、8〜15歳 CHF 22（ゴンドラは別料金）",
        parking_note="Kriens のゴンドラ乗り場（住所）から約30分で Fräkmüntegg へ",
        tips_ja="ロープパークは8歳から（身長120cm以上、11歳未満は大人といっしょ）。小さい子は長いそりコース Fräkigaudi が楽しめます。",
    ),
    "Brunni Engelberg": dict(
        official_url="https://www.brunni.ch", address="Wydenstrasse 55, 6390 Engelberg",
        hours_note="夏と冬。時間と料金は公式サイトで確認",
        price_note="ロープウェイが有料（料金は公式サイトで確認）", food_note="カフェとレストランあり",
        tips_ja="Ristis の駅の横に大きな遊び場（水遊び、トランポリン、すべり台）。宝箱をさがす Globi の宝探しや、はだしで歩く道もあります。冬はそりと雪遊び。",
    ),
    "Mooraculum Rossweid": dict(
        address="Hinterschöniseistrasse 4, 6174 Sörenberg",
        hours_note="夏のあいだ（ゴンドラの運行日）", price="partly",
        price_note="遊び場は無料。ゴンドラは有料",
        parking_note="Rossweid ゴンドラのふもとの駅に駐車場（住所はゴンドラ会社）",
        food_note="ピクニック場とたき火の場所あり",
    ),
}


def apply(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    for name, fields in SPOTS.items():
        spot = FamilySpot.objects.filter(name=name).first()
        if spot is None:
            continue
        for field, value in fields.items():
            if field in CORRECTED or not getattr(spot, field):
                setattr(spot, field, value)
        if spot.checked_on is None:
            spot.checked_on = CHECKED
            spot.status = "published"
        spot.save()


class Migration(migrations.Migration):

    dependencies = [
        ("outings", "0023_family_spot_checked_2"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
