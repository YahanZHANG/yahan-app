"""Publish the family spots whose address, price and season were checked
on their official or tourism-office pages on 2026-11-07 (batch 1: Zurich
area). Only empty fields are filled, so edits made in admin are kept."""

import datetime

from django.db import migrations

CHECKED = datetime.date(2026, 11, 7)

SPOTS = {
    "Zoo Zürich": dict(
        official_url="https://www.zoo.ch", address="Zürichbergstrasse 221, 8044 Zürich",
        hours_note="毎日。3〜10月 9:00〜18:00、11〜2月 9:00〜17:00",
        price_note="大人 CHF 32、6〜12歳 CHF 18", food_note="園内にレストランあり",
    ),
    "Juckerhof": dict(
        official_url="https://www.juckerfarm.ch", address="Dorfstrasse 23, 8607 Seegräben",
        hours_note="季節で変わるので公式サイトで確認",
        price_note="農場と遊び場は無料。体験やイベントは有料のことも",
        parking_note="駐車場あり（近くに有料の駐車場も）", food_note="農場レストランあり。週末はブランチも",
        tips_ja="ヤギ、わらの砦、自然の遊び場、りんご畑の迷路があります。秋はかぼちゃの展示が有名で、週末はとても混みます。",
    ),
    "Bächlihof": dict(
        official_url="https://www.juckerfarm.ch", address="Blaubrunnenstrasse 70, 8645 Jona",
        hours_note="季節で変わるので公式サイトで確認",
        price_note="農場と遊び場は無料。ポニー乗りやかぼちゃ彫りは有料",
        parking_note="農場に駐車場はなし。Sportanlage Grünfeld の有料駐車場か、バス991/992で Grünfeld 下車",
        food_note="レストランと農場の売店あり",
        tips_ja="わらのトランポリン、砂場、動物へのえさやり、自然の遊び場があります。",
    ),
    "Swiss Science Center Technorama": dict(
        official_url="https://www.technorama.ch", address="Technoramastrasse 1, 8404 Winterthur",
        hours_note="毎日 10:00〜17:00", price_note="大人 CHF 34、6〜15歳 CHF 21、5歳以下無料",
    ),
    "Naturmuseum Winterthur": dict(
        official_url="https://stadt.winterthur.ch/naturmuseum", address="Museumstrasse 52, 8400 Winterthur",
        hours_note="火〜日 10:00〜17:00（月曜休み）", price="partly",
        price_note="大人 CHF 5、16歳未満は無料",
        tips_ja="3〜8歳向けの「Kerala」コーナーでは、アナグマの巣穴や自然の遊び箱で遊べます（大人の付き添いが必要）。",
    ),
    "Lindt Home of Chocolate": dict(
        official_url="https://www.lindt-home-of-chocolate.com", address="Schokoladenplatz 1, 8802 Kilchberg",
        hours_note="毎日 10:00〜19:00", price_note="大人 CHF 17、8〜15歳 CHF 10、7歳以下無料",
        food_note="カフェあり", tips_ja="博物館はネット予約がおすすめ。ショップ、カフェ、チョコの噴水はチケットなしで見られます。",
    ),
    "Tram-Museum Zürich": dict(
        official_url="https://www.tram-museum.ch", address="Forchstrasse 260, 8008 Zürich",
        hours_note="月・水・土・日 13:00〜18:00（火・木・金は休み）", price_note="大人 CHF 14、6〜16歳 CHF 7",
    ),
    "Landesmuseum Zürich": dict(
        official_url="https://www.landesmuseum.ch", address="Museumstrasse 2, 8001 Zürich",
        price="partly", price_note="大人 CHF 10、16歳以下は無料",
        hours_note="月曜休み。時間は公式サイトで確認",
        tips_ja="7歳からの探検セット（地図・虫めがね・パズル）や、子ども向けのガイドツアーがあります。",
    ),
    "FIFA Museum": dict(
        official_url="https://www.fifamuseum.com", address="Seestrasse 27, 8002 Zürich",
        hours_note="火〜日 10:00〜18:00（月曜休み）", price_note="大人 CHF 26、7〜15歳 CHF 15、6歳以下無料",
    ),
    "Zoologisches Museum der Universität Zürich": dict(
        official_url="https://www.zm.uzh.ch", address="Karl-Schmid-Strasse 4, 8006 Zürich",
        hours_note="火〜日 10:00〜17:00（月曜休み）", price_note="無料（出口で寄付できます）",
    ),
    "Zuschauerterrasse B Flughafen Zürich": dict(
        official_url="https://www.flughafen-zuerich.ch/passagierterrassen", address="Flughafen Zürich, 8058 Zürich-Flughafen",
        hours_note="毎日。冬 10:00〜17:00、夏 10:00〜18:00",
        price_note="有料。毎月15日は無料（料金は公式サイトで確認）",
    ),
    "Umwelt Arena Schweiz": dict(
        official_url="https://www.umweltarena.ch", address="Türliackerstrasse 4, 8957 Spreitenbach",
        hours_note="水〜日 10:00〜17:00（月・火は休み）", price_note="大人 CHF 21、6〜15歳 CHF 16、5歳以下無料",
    ),
    "Schweizer Kindermuseum": dict(
        official_url="https://www.kindermuseum.ch", address="Ländliweg 7, 5400 Baden",
        hours_note="火〜土 14:00〜17:00、日 10:00〜17:00（月曜休み）", price_note="大人 CHF 12、子ども CHF 5",
    ),
    "Schloss Kyburg": dict(
        official_url="https://www.schlosskyburg.ch", address="Schloss Kyburg, 8314 Kyburg",
        hours_note="4月1日〜10月31日。火〜日 10:00〜17:30（月曜休み）", price_note="大人 CHF 12、子ども CHF 5",
    ),
    "Höllgrotten Baar": dict(
        official_url="https://www.hoellgrotten.ch", address="Höllgrotten, 6340 Baar",
        hours_note="4〜10月。毎日 9:00〜17:00", price_note="大人 CHF 12、6〜16歳 CHF 6、5歳以下無料",
    ),
    "Alpamare": dict(
        official_url="https://www.alpamare.ch", address="Gwattstrasse 12, 8808 Pfäffikon SZ",
        hours_note="月〜木・日 10:00〜21:00、金・土 10:00〜22:00",
        price_note="4時間：大人 CHF 46、6〜15歳 CHF 37（1日券は大人 CHF 49、子ども CHF 40）",
    ),
    "Conny-Land": dict(
        official_url="https://www.connyland.ch", address="Connylandstrasse, 8564 Lipperswil",
        hours_note="2026年は4月2日〜10月18日。10:00から",
        price_note="12歳以上 CHF 40、12歳未満 CHF 36（3日前までのネット予約で安くなる）",
    ),
    "Walter Zoo": dict(
        official_url="https://www.walterzoo.ch", address="Neuchlen 200, 9200 Gossau SG",
        hours_note="時間と料金は公式サイトで確認",
        parking_note="駐車場あり（少なめ。電車とバスがおすすめ）", food_note="セルフサービスのレストランあり。池のそばにバーベキュー場も",
    ),
}


def apply(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    for name, fields in SPOTS.items():
        spot = FamilySpot.objects.filter(name=name).first()
        if spot is None:
            continue
        for field, value in fields.items():
            if field == "price" or not getattr(spot, field):
                setattr(spot, field, value)
        if spot.checked_on is None:
            spot.checked_on = CHECKED
            spot.status = "published"
        spot.save()


class Migration(migrations.Migration):

    dependencies = [
        ("outings", "0021_family_spot_emoji"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
