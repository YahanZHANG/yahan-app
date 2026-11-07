"""Add the 64 places from Taro's list of family spots as drafts.

The list was made with an AI tool, so every place stays a draft until its
address, price and opening season are checked on the official site; then
the admin publishes it. Also fills the new age / language / season / trip
fields of the 6 places published in 0018.
"""

from django.db import migrations

# name, name_ja, kind, canton, town, age_min, age_max, language, season,
# rainy_ok, price, trip, summary_ja
SPOTS = [
    ("Zoo Zürich", "チューリッヒ動物園", "animals", "ZH", "Zürich", 1, 12, "none", "year", False, "paid", "day",
     "ゾウやペンギン、熱帯雨林の館まで、一日かけて回れる大きな動物園。"),
    ("Juckerhof", "ユッカーホフ農場", "farm", "ZH", "Seegräben", 1, 12, "none", "warm", False, "partly", "day",
     "湖のそばの農場。遊び場があり、秋は大きなかぼちゃの展示が名物。"),
    ("Bächlihof", "ベヒリホフ農場", "farm", "SG", "Jona", 1, 12, "none", "warm", False, "partly", "day",
     "季節の野菜が並ぶ農場。遊び場があり、秋はかぼちゃで賑わう。"),
    ("Swiss Science Center Technorama", "テクノラマ科学館", "museum", "ZH", "Winterthur", 5, 15, "little", "year", True, "paid", "day",
     "さわって試せる科学の展示がたくさん。実験ショーもある。"),
    ("Naturmuseum Winterthur", "ヴィンタートゥール自然博物館", "museum", "ZH", "Winterthur", 3, 9, "little", "year", True, "free", "day",
     "小さな子向けのコーナーがある自然の博物館。入場無料。"),
    ("Lindt Home of Chocolate", "リンツ チョコレート博物館", "museum", "ZH", "Kilchberg", 5, None, "none", "year", True, "paid", "day",
     "チョコレートができるまでを見て、最後は試食。大きなチョコの噴水がある。"),
    ("Tram-Museum Zürich", "チューリッヒ路面電車博物館", "museum", "ZH", "Zürich", 2, 10, "little", "year", True, "paid", "day",
     "昔のトラムが並び、車内にも入れる。乗り物好きの子に。"),
    ("Landesmuseum Zürich", "スイス国立博物館", "museum", "ZH", "Zürich", 5, 12, "helps", "year", True, "paid", "day",
     "スイスの歴史の博物館。子ども向けの体験コーナーがある。"),
    ("FIFA Museum", "FIFAミュージアム", "museum", "ZH", "Zürich", 5, 15, "little", "year", True, "paid", "day",
     "サッカーの博物館。体を動かすゲームのコーナーがある。"),
    ("Zoologisches Museum der Universität Zürich", "チューリッヒ大学 動物博物館", "museum", "ZH", "Zürich", 3, 12, "little", "year", True, "free", "day",
     "動物のはく製がたくさん並ぶ、入場無料の博物館。"),
    ("Zuschauerterrasse B Flughafen Zürich", "チューリッヒ空港 展望デッキB", "other", "ZH", "Kloten", 2, 12, "none", "year", False, "paid", "day",
     "飛行機の離着陸を間近で見られる展望デッキ。"),
    ("Umwelt Arena Schweiz", "ウムヴェルト・アレーナ", "museum", "AG", "Spreitenbach", 5, 15, "helps", "year", True, "paid", "day",
     "エネルギーや乗り物、環境のことを体験しながら学べる施設。"),
    ("Schweizer Kindermuseum", "スイス子ども博物館", "museum", "AG", "Baden", 3, 12, "helps", "year", True, "paid", "day",
     "昔のおもちゃや遊びの博物館。遊べる展示が多い。"),
    ("Schloss Kyburg", "キーブルク城", "history", "ZH", "Kyburg", 4, 12, "helps", "warm", False, "paid", "day",
     "中世のお城。昔の暮らしや騎士の世界を体験できる。"),
    ("Höllgrotten Baar", "ヘルグロッテン鍾乳洞", "nature", "ZG", "Baar", 4, 12, "little", "warm", True, "paid", "day",
     "森の中の鍾乳洞。地下を探検する気分で歩ける。"),
    ("Alpamare", "アルパマーレ", "water", "SZ", "Pfäffikon SZ", 3, 15, "none", "year", True, "paid", "day",
     "ウォータースライダーがたくさんある屋内プール。"),
    ("Conny-Land", "コニーランド", "theme", "TG", "Lipperswil", 4, 14, "little", "warm", False, "paid", "day",
     "乗り物やショーのある遊園地。"),
    ("Walter Zoo", "ヴァルター動物園", "animals", "SG", "Gossau SG", 1, 12, "none", "year", False, "paid", "day",
     "動物と遊び場がそろった動物園。サーカス風のショーもある。"),
    ("Baumwipfelpfad Neckertal", "ネッカータール 木のこずえの道", "nature", "SG", "Mogelsberg", 3, 12, "none", "warm", False, "paid", "day",
     "木のこずえの高さを歩ける空中の遊歩道。遊び場もある。"),
    ("Atzmännig", "アツメンニッヒ", "mountain", "SG", "Goldingen", 3, 15, "none", "year", False, "partly", "day",
     "夏はそりコースやロープの遊び場、冬は雪遊びができる山。"),
    ("Heididorf", "ハイジ村", "theme", "GR", "Maienfeld", 3, 12, "little", "warm", False, "paid", "day",
     "ハイジの家を再現した村。物語の世界を歩ける。"),
    ("Arosa Bärenland", "アローザ・ベアランド", "animals", "GR", "Arosa", 3, 12, "none", "warm", False, "paid", "overnight",
     "保護されたクマが暮らす山の公園。"),
    ("Eichhörnliweg Arosa", "アローザ リスの小道", "nature", "GR", "Arosa", 2, 12, "none", "warm", False, "free", "overnight",
     "森の中でリスに会える散歩道。"),
    ("Madrisa-Land", "マドリーザ・ランド", "mountain", "GR", "Klosters", 2, 12, "none", "summer", False, "paid", "overnight",
     "山の上の大きな遊び場。ゴンドラで上がる。"),
    ("Globi Erlebnisweg", "グロビの体験の道", "theme", "GR", "", 3, 12, "little", "summer", False, "partly", "overnight",
     "スイスの人気キャラクター、グロビがテーマの散策路。"),
    ("Pradaschier Rodelbahn", "プラダシエール そり滑り", "mountain", "GR", "Churwalden", 5, 15, "none", "warm", False, "paid", "both",
     "山を一気に下るレールのそり。"),
    ("Caumasee", "カウマ湖", "water", "GR", "Flims", 1, 15, "none", "summer", False, "partly", "overnight",
     "森に囲まれたエメラルド色の湖。夏は水遊び。"),
    ("Freestyle Academy LAAX", "LAAX フリースタイル・アカデミー", "indoor", "GR", "Laax", 5, 15, "little", "year", True, "paid", "overnight",
     "トランポリンやスケートの屋内施設。"),
    ("Muottas Muragl", "ムオタス・ムラーユ", "mountain", "GR", "Samedan", 3, 15, "none", "summer_winter", False, "paid", "overnight",
     "ケーブルカーで上がる展望の山。冬はそり滑り。"),
    ("Verkehrshaus der Schweiz", "スイス交通博物館", "museum", "LU", "Luzern", 3, 15, "little", "year", True, "paid", "day",
     "鉄道や飛行機、宇宙まで、乗り物の大きな博物館。"),
    ("Glasi Hergiswil", "グラージ・ヘルギスヴィル", "museum", "NW", "Hergiswil", 4, 12, "little", "year", True, "partly", "day",
     "ガラス作りを目の前で見られる工房。ガラスの迷路もある。"),
    ("Natur- und Tierpark Goldau", "ゴルダウ動物自然公園", "animals", "SZ", "Goldau", 1, 12, "none", "year", False, "paid", "day",
     "シカにえさをあげながら歩ける、森の中の動物公園。"),
    ("Rigi", "リギ山", "mountain", "SZ", "Vitznau", 1, 12, "none", "year", False, "paid", "day",
     "登山鉄道で上がる展望の山。冬は雪遊び。"),
    ("Seilpark Pilatus Fräkmüntegg", "ピラトゥス フレックミュンテック", "mountain", "LU", "Kriens", 4, 15, "none", "warm", False, "paid", "day",
     "ロープパークや森の遊び場がある山の中腹。"),
    ("Brunni Engelberg", "ブルンニ（エンゲルベルク）", "mountain", "OW", "Engelberg", 3, 12, "little", "summer_winter", False, "paid", "both",
     "山の上の遊び場や宝探しの道。冬は雪遊び。"),
    ("Titlis", "ティトリス", "mountain", "OW", "Engelberg", 5, 15, "none", "year", False, "paid", "both",
     "一年中雪がある山。氷河の洞窟やロープウェイが楽しい。"),
    ("Mooraculum Rossweid", "ムーラクルム（ロスヴァイト）", "mountain", "LU", "Sörenberg", 2, 12, "none", "summer", False, "paid", "both",
     "湿地の中で水遊びができる、山の上の遊び場。"),
    ("Zwerg Bartli Erlebnisweg", "小人バルトリの体験の道", "theme", "GL", "Braunwald", 3, 10, "little", "warm", False, "partly", "both",
     "小人のお話をたどる山の散策路。"),
    ("Gurtenpark", "グルテン公園", "park", "BE", "Wabern bei Bern", 1, 12, "none", "warm", False, "partly", "day",
     "ベルンの丘の上の公園。ミニ鉄道や大きな遊具がある。"),
    ("Museum für Kommunikation", "通信博物館", "museum", "BE", "Bern", 5, 15, "helps", "year", True, "paid", "day",
     "通信やデジタルを遊びながら体験できる博物館。"),
    ("Tierpark Dählhölzli", "ダールヘルツリ動物園", "animals", "BE", "Bern", 1, 12, "none", "year", False, "partly", "day",
     "川沿いの動物園。外の動物は無料で見られる。"),
    ("Freilichtmuseum Ballenberg", "バレンベルク野外博物館", "history", "BE", "Hofstetten bei Brienz", 3, 12, "little", "warm", False, "paid", "overnight",
     "スイス各地の昔の家が集まる、広い野外博物館。"),
    ("Trauffer Erlebniswelt", "トラウファー体験ワールド", "museum", "BE", "Hofstetten bei Brienz", 3, 12, "little", "year", True, "paid", "overnight",
     "木の牛のおもちゃ工房。色ぬり体験ができる。"),
    ("St. Beatus-Höhlen", "聖ベアトゥス洞窟", "nature", "BE", "Sundlauenen", 5, 15, "little", "warm", True, "paid", "overnight",
     "湖の上の大きな鍾乳洞。冒険気分で歩ける。"),
    ("Muggestutz Erlebnisweg", "ムッゲシュトゥッツの体験の道", "theme", "BE", "Hasliberg", 3, 10, "little", "summer", False, "paid", "overnight",
     "小人のお話をたどる山の遊び道。"),
    ("Allmendhubel Flower Park", "アルメンドフーベル フラワーパーク", "mountain", "BE", "Mürren", 2, 12, "none", "summer", False, "paid", "overnight",
     "花畑と山の景色の中にある遊び場。"),
    ("Oeschinensee", "エッシネン湖", "nature", "BE", "Kandersteg", 3, 15, "none", "summer_winter", False, "paid", "overnight",
     "山に囲まれた湖。夏はレールのそりもある。"),
    ("Grindelwald First", "グリンデルワルト・フィルスト", "mountain", "BE", "Grindelwald", 5, 15, "none", "summer", False, "paid", "overnight",
     "景色の良い山。夏は山の乗り物や遊びがいろいろ。"),
    ("Zoo Basel", "バーゼル動物園", "animals", "BS", "Basel", 1, 12, "none", "year", False, "paid", "day",
     "街の中にある動物園。屋内の展示もある。"),
    ("Augusta Raurica", "アウグスタ・ラウリカ", "history", "BL", "Augst", 5, 15, "helps", "warm", False, "partly", "day",
     "古代ローマの遺跡。毎年夏にローマ祭がある。"),
    ("aquabasilea", "アクアバジレア", "water", "BL", "Pratteln", 3, 15, "none", "year", True, "paid", "day",
     "すべり台のある屋内プール。"),
    ("MUKS Museum Kultur & Spiel Riehen", "MUKS 文化と遊びの博物館", "museum", "BS", "Riehen", 3, 12, "helps", "year", True, "paid", "day",
     "おもちゃと遊びの博物館。工作もできる。"),
    ("Papiliorama", "パピリオラマ", "animals", "FR", "Kerzers", 2, 12, "none", "year", True, "paid", "both",
     "熱帯の蝶が舞う館と、夜の動物の館がある。"),
    ("Maison Cailler", "メゾン・カイエ", "museum", "FR", "Broc", 5, None, "none", "year", True, "paid", "overnight",
     "スイスのチョコレート工場。作り方を見て試食できる。"),
    ("Signal de Bougy", "シニャル・ド・ブジー", "park", "VD", "Bougy-Villars", 1, 12, "none", "warm", False, "partly", "overnight",
     "レマン湖を見下ろす公園。大きな遊具やミニ鉄道がある。"),
    ("AQUATIS Aquarium-Vivarium", "アクアティス水族館", "animals", "VD", "Lausanne", 2, 12, "none", "year", True, "paid", "overnight",
     "淡水の魚や爬虫類の水族館。"),
    ("Alimentarium", "アリメンタリウム（食の博物館）", "museum", "VD", "Vevey", 5, 15, "helps", "year", True, "paid", "overnight",
     "食べ物の博物館。料理のワークショップもある。"),
    ("Swiss Vapeur Parc", "スイス・ヴァプール・パーク", "theme", "VS", "Le Bouveret", 2, 12, "none", "warm", False, "paid", "overnight",
     "小さな蒸気機関車に乗って園内を回れる。"),
    ("Aquaparc", "アクアパルク", "water", "VS", "Le Bouveret", 3, 15, "none", "year", True, "paid", "overnight",
     "すべり台がたくさんある屋内プール。"),
    ("Chaplin's World", "チャップリンズ・ワールド", "museum", "VD", "Corsier-sur-Vevey", 6, 15, "little", "year", True, "paid", "overnight",
     "チャップリンの映画の世界に入り込める博物館。"),
    ("Swissminiatur", "スイスミニチュア", "theme", "TI", "Melide", 2, 12, "none", "warm", False, "paid", "overnight",
     "スイスの名所のミニチュアとミニ鉄道。"),
    ("Monte Tamaro", "モンテ・タマロ", "mountain", "TI", "Rivera", 4, 15, "none", "warm", False, "paid", "overnight",
     "レールのそりやロープパークがある山。"),
    ("Falconeria Locarno", "ロカルノ鷹匠センター", "animals", "TI", "Locarno", 3, 12, "little", "warm", False, "paid", "overnight",
     "ワシやフクロウが飛ぶショーを見られる。"),
    ("Castelgrande", "カステルグランデ", "history", "TI", "Bellinzona", 4, 15, "little", "year", False, "partly", "overnight",
     "世界遺産のお城。城壁の上を歩ける。"),
]

# Extra fields for the places already published in 0018.
EXISTING = {
    "Park im Grüene": dict(age_min=1, age_max=10, language="none", season="year", trip="day"),
    "Wildnispark Zürich Langenberg": dict(age_min=1, age_max=12, language="none", season="year", trip="day"),
    "Freiruum Zug": dict(age_min=2, age_max=7, language="none", season="year", trip="day"),
    "EBIANUM Baggermuseum": dict(age_min=2, age_max=12, language="none", season="year", trip="day"),
    "Knies Kinderzoo": dict(age_min=1, age_max=10, language="none", season="warm", trip="day"),
    "Sauriermuseum Aathal": dict(age_min=3, age_max=12, language="little", season="year", trip="day"),
}


def add_spots(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    for name, fields in EXISTING.items():
        FamilySpot.objects.filter(name=name).update(**fields)
    for order, row in enumerate(SPOTS, start=1):
        (name, name_ja, kind, canton, town, age_min, age_max, language, season,
         rainy_ok, price, trip, summary_ja) = row
        FamilySpot.objects.get_or_create(
            name=name,
            defaults=dict(
                name_ja=name_ja, kind=kind, canton=canton, town=town,
                age_min=age_min, age_max=age_max, language=language, season=season,
                rainy_ok=rainy_ok, price=price, trip=trip, summary_ja=summary_ja,
                status="draft", sort_order=100 + order,
            ),
        )


def remove_spots(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    FamilySpot.objects.filter(name__in=[row[0] for row in SPOTS], status="draft").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("outings", "0019_family_spot_details"),
    ]

    operations = [
        migrations.RunPython(add_spots, remove_spots),
    ]
