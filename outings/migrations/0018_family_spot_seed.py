from datetime import date

from django.db import migrations


# First spots, recommended by families in Taro's circle (2026-11-07).
# Facts checked on the official or tourism sites that day; the text is our own.
SPOTS = [
    {
        "name": "Park im Grüene",
        "name_ja": "パーク・イム・グリューネ",
        "kind": "park",
        "canton": "ZH",
        "town": "Rüschlikon",
        "address": "Alsenstrasse 40, 8803 Rüschlikon",
        "summary_ja": "チューリッヒ湖を見下ろす、ミグロが運営する大きな公園。大型の遊具がそろい、園内のレストランで休憩もできます。",
        "tips_ja": "天気のよい水曜・日曜の午後は、ミニ列車やロバ乗り（各CHF 1、春〜秋）や人形劇（無料・屋外）があることも。向かいのスーパーは日曜休み。",
        "price": "partly",
        "price_note": "入園無料。ミニ列車・ロバ乗りは1回CHF 1",
        "open_sunday": True,
        "hours_note": "毎日。冬（11〜2月）8:00〜16:00、夏（5〜8月）8:00〜19:00",
        "food_note": "園内にセルフサービスのレストラン（日曜・祝日はブランチあり）",
        "maps_url": "https://maps.app.goo.gl/HJ5yJUo1Zje4AducA",
        "sort_order": 10,
    },
    {
        "name": "Wildnispark Zürich Langenberg",
        "name_ja": "ランゲンベルク野生動物公園",
        "kind": "animals",
        "canton": "ZH",
        "town": "Langnau am Albis",
        "address": "Albisstrasse 4, 8135 Langnau am Albis",
        "summary_ja": "クマやオオカミ、ヘラジカ、イノシシなど、スイスの森にすむ動物を広い囲いの中で見られる動物公園。入園は無料です。",
        "tips_ja": "森の中の道なので、歩きやすい靴で。ベビーカーでも回れます。",
        "price": "free",
        "price_note": "入園無料（駐車場は有料）",
        "open_sunday": True,
        "hours_note": "毎日。西エリアは9:00〜16:00",
        "parking_note": "有料",
        "stroller_ok": True,
        "official_url": "https://www.wildnispark.ch",
        "maps_url": "https://maps.app.goo.gl/goJM6MGevzSfp8Gw9",
        "sort_order": 20,
    },
    {
        "name": "Freiruum Zug",
        "name_ja": "フライルーム（ツーク）",
        "kind": "indoor",
        "canton": "ZG",
        "town": "Zug",
        "address": "Aabachstrasse 16, 6300 Zug",
        "summary_ja": "古い工場を使った大きな屋内施設。子どもの室内遊び場やトランポリンがあり、フードコートやカフェもあるので雨の日にぴったりです。",
        "tips_ja": "室内遊び場は有料で予約制。支払いはカードやTWINTのみ（現金不可）。",
        "rainy_ok": True,
        "price": "partly",
        "price_note": "入館無料。遊び場は有料・予約制",
        "open_sunday": True,
        "hours_note": "公式サイトで確認",
        "food_note": "マーケットホールのフードコート、ロースタリーのカフェ",
        "age_note": "室内遊び場は2〜7歳向け",
        "official_url": "https://www.freiruum.ch",
        "maps_url": "https://maps.app.goo.gl/mHK2thKQKPvbJHGn8",
        "sort_order": 30,
    },
    {
        "name": "EBIANUM Baggermuseum",
        "name_ja": "エビアヌム重機博物館",
        "kind": "museum",
        "canton": "AG",
        "town": "Fisibach",
        "address": "Museumstrasse 1, 5467 Fisibach",
        "summary_ja": "ショベルカーやブルドーザーなど、昔から今までの重機がずらりと並ぶ博物館。乗り物好きの子どもにはたまりません。",
        "tips_ja": "屋外テラスの砂場では、子ども用の電動ショベルを動かせます。",
        "rainy_ok": True,
        "price": "paid",
        "open_sunday": True,
        "hours_note": "水・土・日・祝日 10:00〜17:00",
        "parking_note": "建物の前に無料駐車場",
        "food_note": "館内にカフェ",
        "stroller_ok": True,
        "official_url": "https://www.ebianum.ch",
        "maps_url": "https://maps.app.goo.gl/6hrYqFE3GUvnH5su6",
        "sort_order": 40,
    },
    {
        "name": "Knies Kinderzoo",
        "name_ja": "クニー子ども動物園",
        "kind": "animals",
        "canton": "SG",
        "town": "Rapperswil-Jona",
        "address": "Oberseestrasse 36, 8640 Rapperswil",
        "summary_ja": "こぢんまりとした雰囲気のよい動物園。ゾウを上の橋から眺めたり、キリンにえさをあげたり、ポニーやラクダに乗ったりできます。",
        "tips_ja": "冬は休園（2026年11月2日〜2027年1月29日）。1月30日から再開します。",
        "price": "paid",
        "price_note": "大人CHF 23、子ども（4〜15歳）CHF 9",
        "open_sunday": True,
        "hours_note": "冬は休園。営業期間は公式サイトで確認",
        "official_url": "https://www.knieskinderzoo.ch",
        "maps_url": "https://maps.app.goo.gl/9EpBDBdt22AdGrpM9",
        "sort_order": 50,
    },
    {
        "name": "Sauriermuseum Aathal",
        "name_ja": "アータール恐竜博物館",
        "kind": "museum",
        "canton": "ZH",
        "town": "Aathal",
        "address": "Zürichstrasse 69, 8607 Aathal",
        "summary_ja": "実物大の恐竜の骨格や化石が並ぶ博物館。思ったより大きく、子どもが夢中になります。",
        "tips_ja": "庭に遊び場とピクニックスペースがあります。月曜は休館。",
        "rainy_ok": True,
        "price": "paid",
        "price_note": "大人CHF 22、子ども（5〜16歳）CHF 11、4歳CHF 6",
        "open_sunday": True,
        "hours_note": "火〜土 10:00〜17:00、日 10:00〜18:00（月曜休館）",
        "parking_note": "無料駐車場あり",
        "food_note": "館内にカフェテリア",
        "official_url": "https://www.sauriermuseum.ch",
        "maps_url": "https://maps.app.goo.gl/QCHX3xGLTioCP3fHA",
        "sort_order": 60,
    },
]


def add_spots(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    for data in SPOTS:
        FamilySpot.objects.get_or_create(
            name=data["name"],
            defaults={**data, "status": "published", "checked_on": date(2026, 11, 7)},
        )


def remove_spots(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    FamilySpot.objects.filter(name__in=[s["name"] for s in SPOTS]).delete()


class Migration(migrations.Migration):

    dependencies = [("outings", "0017_family_spot")]

    operations = [migrations.RunPython(add_spots, remove_spots)]
