"""Publish the family spots checked on their official or tourism-office
pages on 2026-11-07 (batch 2: eastern Switzerland and Graubünden). Only
empty fields are filled, so edits made in admin are kept; price, age and
season are corrected because the first guesses were wrong."""

import datetime

from django.db import migrations

CHECKED = datetime.date(2026, 11, 7)
CORRECTED = {"price", "age_min", "season"}

SPOTS = {
    "Baumwipfelpfad Neckertal": dict(
        address="Lettenstrasse 19, 9122 Mogelsberg",
        hours_note="季節で変わるので公式サイトで確認",
        price_note="大人 CHF 15、6〜16歳 CHF 8、6歳未満無料、家族 CHF 40",
        parking_note="駐車場あり", food_note="レストランと遊び場あり",
    ),
    "Atzmännig": dict(
        official_url="https://www.atzmaennig.ch", address="Atzmännigstrasse, 8638 Goldingen",
        hours_note="季節とリフトで変わるので公式サイトで確認",
        price_note="遊び場は無料。そりコースやロープの遊び場は有料",
        food_note="山のレストランあり",
        tips_ja="夏はそりコース、トランポリン、ふれあい動物、ボート、ゴーカート、ロープの遊び場。冬はスキーと雪遊び。",
    ),
    "Heididorf": dict(
        official_url="https://www.heididorf.ch", address="Bovelweg 16, 7304 Maienfeld",
        hours_note="時間と料金は公式サイトで確認。5〜10月の土日祝は Maienfeld 駅からハイジバスあり",
        price_note="有料（料金は公式サイトで確認）",
        parking_note="Heidihof のそばに無料の駐車場あり", food_note="となりに Hotel Restaurant Heidihof",
    ),
    "Arosa Bärenland": dict(
        official_url="https://arosabaerenland.swiss", address="Arosa Bärenland, 7050 Arosa",
        hours_note="夏のあいだ。時間は公式サイトで確認",
        price_note="ロープウェイが有料（料金は公式サイトで確認）",
        parking_note="Arosa-Weisshorn ロープウェイの中間駅にあり、車では行けません。Arosa の Obersee 駐車場などに停めて、ロープウェイで上がります",
        tips_ja="車いすでも回れる道です。クマは冬眠するので、夏に行きましょう。",
    ),
    "Eichhörnliweg Arosa": dict(
        address="Eichhörnliweg, 7050 Arosa", parking_note="Arosa 駅の裏から歩きはじめます", price_note="無料",
        hours_note="一年じゅう歩けます", season="year",
        tips_ja="リス用のナッツを持って行くと、手から食べに来てくれることも。ベビーカーでもなんとか歩けます。",
    ),
    "Zwerg Bartli Erlebnisweg": dict(
        official_url="https://braunwald.ch", address="Zwerg Bartli Erlebnisweg, 8784 Braunwald",
        hours_note="6月中旬〜10月末",
        price_note="道は無料。ケーブルカーは有料（家族パスあり）",
        parking_note="Braunwald は車が入れない村。Linthal のケーブルカー乗り場に駐車場",
        tips_ja="短いコースは1時間ほど。Grotzenbüel から山の駅までのコースはベビーカー向きです。",
    ),
    "Madrisa-Land": dict(
        official_url="https://www.madrisa.ch", address="Madrisastrasse 7, 7252 Klosters Dorf",
        hours_note="夏のあいだ。時間は公式サイトで確認", price="partly",
        price_note="遊び場は無料。ゴンドラは有料。玉ころがしの玉は CHF 2（現金）",
        parking_note="駐車場あり", food_note="山のレストランあり",
    ),
    "Caumasee": dict(
        address="Via dil Lag, 7017 Flims",
        hours_note="泳げるのは2026年は5月16日〜8月30日（監視員は 8:30〜17:00）",
        price_note="大人 CHF 18、6〜17歳 CHF 9（ゲストカードで割引）",
        parking_note="バス停 Flims Caumasee から歩いて約500m。湖まで無料のケーブルカーあり",
        food_note="セルフサービスのレストランと売店あり。バーベキューはできません",
    ),
    "Pradaschier Rodelbahn": dict(
        address="Girabodawäg 16, 7075 Churwalden", age_min=3, season="year",
        hours_note="冬もやっています。時間と料金は現地の公式情報で確認",
        price_note="有料", parking_note="駐車場あり", food_note="ふもとの駅にレストランあり",
        tips_ja="3歳から大人といっしょに乗れます。ひとりで乗れるのは8歳以上で身長135cm以上。",
    ),
    "Muottas Muragl": dict(
        official_url="https://www.muottasmuragl.ch", address="Punt Muragl 3, 7503 Samedan", parking_note="ふもとのケーブルカー乗り場の住所です",
        hours_note="夏と冬。時間と料金は公式サイトで確認",
        price_note="ケーブルカーが有料",
        tips_ja="夏は山の上に遊び場があります。冬はそりコースもあります。",
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
        ("outings", "0022_family_spot_checked_1"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
