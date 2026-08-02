from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from feeding.models import (
    Allergen,
    Dish,
    DishCategory,
    DishIngredient,
    FeedingGroup,
    FeedingGuideline,
    Food,
    FoodCategory,
)


FOOD_CATEGORIES = [
    ("穀類・パン・麺", 10),
    ("いも類", 20),
    ("野菜", 30),
    ("果物", 40),
    ("豆・大豆製品", 50),
    ("魚・魚介類", 60),
    ("肉類", 70),
    ("卵", 80),
    ("乳製品", 90),
    ("海藻", 100),
    ("きのこ", 110),
    ("油・調味料", 120),
    ("その他", 130),
]


DISH_CATEGORIES = [
    ("おかゆ・ごはん", 10),
    ("麺・パスタ", 20),
    ("パン", 30),
    ("野菜料理", 40),
    ("魚料理", 50),
    ("肉料理", 60),
    ("卵料理", 70),
    ("豆腐・大豆料理", 80),
    ("スープ・汁物", 90),
    ("果物・デザート", 100),
    ("市販ベビーフード", 110),
    ("その他", 120),
]

FEEDING_GROUPS = [
    (
        FeedingGroup.Code.GRAIN,
        "穀類",
        10,
    ),
    (
        FeedingGroup.Code.VEGETABLE_FRUIT,
        "野菜・果物",
        20,
    ),
    (
        FeedingGroup.Code.FISH,
        "魚",
        30,
    ),
    (
        FeedingGroup.Code.MEAT,
        "肉",
        40,
    ),
    (
        FeedingGroup.Code.TOFU,
        "豆腐",
        50,
    ),
    (
        FeedingGroup.Code.EGG,
        "卵",
        60,
    ),
    (
        FeedingGroup.Code.DAIRY,
        "乳製品",
        70,
    ),
    (
        FeedingGroup.Code.OTHER,
        "比較対象外",
        999,
    ),
]

ALLERGENS = [
    # 義務表示9品目
    ("えび", Allergen.Classification.REQUIRED, 10),
    ("カシューナッツ", Allergen.Classification.REQUIRED, 20),
    ("かに", Allergen.Classification.REQUIRED, 30),
    ("くるみ", Allergen.Classification.REQUIRED, 40),
    ("小麦", Allergen.Classification.REQUIRED, 50),
    ("そば", Allergen.Classification.REQUIRED, 60),
    ("卵", Allergen.Classification.REQUIRED, 70),
    ("乳", Allergen.Classification.REQUIRED, 80),
    ("落花生（ピーナッツ）", Allergen.Classification.REQUIRED, 90),

    # 推奨表示20品目
    ("アーモンド", Allergen.Classification.RECOMMENDED, 110),
    ("あわび", Allergen.Classification.RECOMMENDED, 120),
    ("いか", Allergen.Classification.RECOMMENDED, 130),
    ("いくら", Allergen.Classification.RECOMMENDED, 140),
    ("オレンジ", Allergen.Classification.RECOMMENDED, 150),
    ("キウイフルーツ", Allergen.Classification.RECOMMENDED, 160),
    ("牛肉", Allergen.Classification.RECOMMENDED, 170),
    ("ごま", Allergen.Classification.RECOMMENDED, 180),
    ("さけ", Allergen.Classification.RECOMMENDED, 190),
    ("さば", Allergen.Classification.RECOMMENDED, 200),
    ("大豆", Allergen.Classification.RECOMMENDED, 210),
    ("鶏肉", Allergen.Classification.RECOMMENDED, 220),
    ("バナナ", Allergen.Classification.RECOMMENDED, 230),
    ("ピスタチオ", Allergen.Classification.RECOMMENDED, 240),
    ("豚肉", Allergen.Classification.RECOMMENDED, 250),
    ("マカダミアナッツ", Allergen.Classification.RECOMMENDED, 260),
    ("もも", Allergen.Classification.RECOMMENDED, 270),
    ("やまいも", Allergen.Classification.RECOMMENDED, 280),
    ("りんご", Allergen.Classification.RECOMMENDED, 290),
    ("ゼラチン", Allergen.Classification.RECOMMENDED, 300),
]


# 各タプルの構造：
# (
#     食材名,
#     食材ジャンル名,
#     アレルゲン名のリスト,
#     1歳までリストに表示するか,
# )
FOODS = [
    # 穀類・パン・麺
    ("米", "穀類・パン・麺", [], True),
    ("米粉", "穀類・パン・麺", [], True),
    ("オートミール", "穀類・パン・麺", [], True),
    ("小麦粉", "穀類・パン・麺", ["小麦"], True),
    ("食パン", "穀類・パン・麺", ["小麦"], True),
    ("うどん", "穀類・パン・麺", ["小麦"], True),
    ("そうめん", "穀類・パン・麺", ["小麦"], True),
    ("パスタ", "穀類・パン・麺", ["小麦"], True),
    ("マカロニ", "穀類・パン・麺", ["小麦"], True),
    ("そば", "穀類・パン・麺", ["そば"], False),

    # いも類
    ("じゃがいも", "いも類", [], True),
    ("さつまいも", "いも類", [], True),
    ("里芋", "いも類", [], True),
    ("長芋", "いも類", ["やまいも"], True),
    ("山芋", "いも類", ["やまいも"], True),

    # 野菜
    ("にんじん", "野菜", [], True),
    ("かぼちゃ", "野菜", [], True),
    ("大根", "野菜", [], True),
    ("かぶ", "野菜", [], True),
    ("玉ねぎ", "野菜", [], True),
    ("トマト", "野菜", [], True),
    ("キャベツ", "野菜", [], True),
    ("白菜", "野菜", [], True),
    ("ブロッコリー", "野菜", [], True),
    ("カリフラワー", "野菜", [], True),
    ("ほうれん草", "野菜", [], True),
    ("小松菜", "野菜", [], True),
    ("チンゲン菜", "野菜", [], True),
    ("レタス", "野菜", [], True),
    ("きゅうり", "野菜", [], True),
    ("なす", "野菜", [], True),
    ("ズッキーニ", "野菜", [], True),
    ("ピーマン", "野菜", [], True),
    ("パプリカ", "野菜", [], True),
    ("とうもろこし", "野菜", [], True),
    ("アスパラガス", "野菜", [], True),
    ("オクラ", "野菜", [], True),
    ("ごぼう", "野菜", [], True),
    ("れんこん", "野菜", [], True),
    ("もやし", "野菜", [], True),

    # 果物
    ("りんご", "果物", ["りんご"], True),
    ("バナナ", "果物", ["バナナ"], True),
    ("もも", "果物", ["もも"], True),
    ("オレンジ", "果物", ["オレンジ"], True),
    ("みかん", "果物", [], True),
    ("キウイフルーツ", "果物", ["キウイフルーツ"], True),
    ("いちご", "果物", [], True),
    ("なし", "果物", [], True),
    ("ぶどう", "果物", [], True),
    ("スイカ", "果物", [], True),
    ("メロン", "果物", [], True),
    ("柿", "果物", [], True),
    ("パイナップル", "果物", [], True),
    ("マンゴー", "果物", [], True),
    ("ブルーベリー", "果物", [], True),
    ("プルーン", "果物", [], True),
    ("アボカド", "果物", [], True),

    # 豆・大豆製品
    ("豆腐", "豆・大豆製品", ["大豆"], True),
    ("高野豆腐", "豆・大豆製品", ["大豆"], True),
    ("納豆", "豆・大豆製品", ["大豆"], True),
    ("きなこ", "豆・大豆製品", ["大豆"], True),
    ("無調整豆乳", "豆・大豆製品", ["大豆"], True),
    ("枝豆", "豆・大豆製品", ["大豆"], True),
    ("大豆", "豆・大豆製品", ["大豆"], True),
    ("グリーンピース", "豆・大豆製品", [], True),
    ("あずき", "豆・大豆製品", [], True),
    ("ひよこ豆", "豆・大豆製品", [], True),
    ("レンズ豆", "豆・大豆製品", [], True),

    # 魚・魚介類
    ("たい", "魚・魚介類", [], True),
    ("ひらめ", "魚・魚介類", [], True),
    ("かれい", "魚・魚介類", [], True),
    ("たら", "魚・魚介類", [], True),
    ("さけ", "魚・魚介類", ["さけ"], True),
    ("まぐろ", "魚・魚介類", [], True),
    ("かつお", "魚・魚介類", [], True),
    ("ぶり", "魚・魚介類", [], True),
    ("いわし", "魚・魚介類", [], True),
    ("あじ", "魚・魚介類", [], True),
    ("さば", "魚・魚介類", ["さば"], True),
    ("しらす", "魚・魚介類", [], True),
    ("ツナ（水煮）", "魚・魚介類", [], True),
    ("えび", "魚・魚介類", ["えび"], False),
    ("かに", "魚・魚介類", ["かに"], False),
    ("いか", "魚・魚介類", ["いか"], False),
    ("いくら", "魚・魚介類", ["いくら"], False),
    ("あわび", "魚・魚介類", ["あわび"], False),

    # 肉類
    ("鶏肉", "肉類", ["鶏肉"], True),
    ("鶏レバー", "肉類", ["鶏肉"], True),
    ("牛肉", "肉類", ["牛肉"], True),
    ("豚肉", "肉類", ["豚肉"], True),

    # 卵
    ("卵黄", "卵", ["卵"], True),
    ("卵白", "卵", ["卵"], True),
    ("全卵", "卵", ["卵"], True),

    # 乳製品
    ("牛乳", "乳製品", ["乳"], True),
    ("プレーンヨーグルト", "乳製品", ["乳"], True),
    ("カッテージチーズ", "乳製品", ["乳"], True),
    ("粉チーズ", "乳製品", ["乳"], True),
    ("バター", "乳製品", ["乳"], True),

    # 海藻
    ("わかめ", "海藻", [], True),
    ("焼きのり", "海藻", [], True),
    ("青のり", "海藻", [], True),
    ("ひじき", "海藻", [], True),
    ("昆布", "海藻", [], True),

    # きのこ
    ("しいたけ", "きのこ", [], True),
    ("しめじ", "きのこ", [], True),
    ("えのき", "きのこ", [], True),
    ("まいたけ", "きのこ", [], True),
    ("マッシュルーム", "きのこ", [], True),

    # 油・調味料
    ("植物油", "油・調味料", [], True),
    ("オリーブ油", "油・調味料", [], True),
    ("ごま油", "油・調味料", ["ごま"], True),
    ("すりごま", "油・調味料", ["ごま"], True),
    ("味噌", "油・調味料", ["大豆"], True),
    ("しょうゆ", "油・調味料", ["小麦", "大豆"], True),
    ("砂糖", "油・調味料", [], True),
    ("塩", "油・調味料", [], True),
    ("かつおだし", "油・調味料", [], True),
    ("昆布だし", "油・調味料", [], True),
    ("ゼラチン", "油・調味料", ["ゼラチン"], False),

    # アレルゲン確認用
    ("落花生（ピーナッツペースト）", "その他", ["落花生（ピーナッツ）"], False),
    ("アーモンド（ペースト・粉末）", "その他", ["アーモンド"], False),
    ("くるみ（ペースト・粉末）", "その他", ["くるみ"], False),
    ("カシューナッツ（ペースト・粉末）", "その他", ["カシューナッツ"], False),
    ("ピスタチオ（ペースト・粉末）", "その他", ["ピスタチオ"], False),
    (
        "マカダミアナッツ（ペースト・粉末）",
        "その他",
        ["マカダミアナッツ"],
        False,
    ),
]

# 各タプルの構造：
# (
#     料理名,
#     料理ジャンル名,
#     材料となる食材名のリスト,
# )
DISHES = [
    # おかゆ・ごはん
    (
        "10倍がゆ",
        "おかゆ・ごはん",
        ["米"],
    ),
    (
        "7倍がゆ",
        "おかゆ・ごはん",
        ["米"],
    ),
    (
        "5倍がゆ",
        "おかゆ・ごはん",
        ["米"],
    ),
    (
        "オートミールがゆ",
        "おかゆ・ごはん",
        ["オートミール"],
    ),
    (
        "野菜がゆ",
        "おかゆ・ごはん",
        ["米", "にんじん", "玉ねぎ", "キャベツ"],
    ),
    (
        "しらすがゆ",
        "おかゆ・ごはん",
        ["米", "しらす"],
    ),
    (
        "鮭がゆ",
        "おかゆ・ごはん",
        ["米", "さけ"],
    ),
    (
        "鶏肉がゆ",
        "おかゆ・ごはん",
        ["米", "鶏肉", "にんじん"],
    ),
    (
        "卵黄がゆ",
        "おかゆ・ごはん",
        ["米", "卵黄"],
    ),
    (
        "納豆がゆ",
        "おかゆ・ごはん",
        ["米", "納豆"],
    ),
    (
        "豆腐がゆ",
        "おかゆ・ごはん",
        ["米", "豆腐"],
    ),
    (
        "トマトリゾット",
        "おかゆ・ごはん",
        ["米", "トマト", "玉ねぎ"],
    ),

    # 麺・パスタ
    (
        "やわらかいうどん",
        "麺・パスタ",
        ["うどん"],
    ),
    (
        "野菜うどん",
        "麺・パスタ",
        ["うどん", "にんじん", "玉ねぎ", "キャベツ"],
    ),
    (
        "鶏肉うどん",
        "麺・パスタ",
        ["うどん", "鶏肉", "にんじん"],
    ),
    (
        "鮭うどん",
        "麺・パスタ",
        ["うどん", "さけ", "ほうれん草"],
    ),
    (
        "トマトパスタ",
        "麺・パスタ",
        ["パスタ", "トマト", "玉ねぎ"],
    ),
    (
        "ボロネーゼ",
        "麺・パスタ",
        ["パスタ", "牛肉", "トマト", "玉ねぎ", "にんじん"],
    ),
    (
        "ツナパスタ",
        "麺・パスタ",
        ["パスタ", "ツナ（水煮）", "トマト", "玉ねぎ"],
    ),
    (
        "クリームパスタ",
        "麺・パスタ",
        ["パスタ", "牛乳", "バター", "ほうれん草"],
    ),
    (
        "野菜マカロニ",
        "麺・パスタ",
        ["マカロニ", "にんじん", "玉ねぎ", "ブロッコリー"],
    ),

    # パン
    (
        "パンがゆ",
        "パン",
        ["食パン"],
    ),
    (
        "ミルクパンがゆ",
        "パン",
        ["食パン", "牛乳"],
    ),
    (
        "バナナパンがゆ",
        "パン",
        ["食パン", "バナナ"],
    ),
    (
        "フレンチトースト",
        "パン",
        ["食パン", "全卵", "牛乳"],
    ),
    (
        "野菜入りパンがゆ",
        "パン",
        ["食パン", "にんじん", "玉ねぎ", "ブロッコリー"],
    ),

    # 野菜料理
    (
        "かぼちゃサラダ",
        "野菜料理",
        ["かぼちゃ", "プレーンヨーグルト"],
    ),
    (
        "ポテトサラダ",
        "野菜料理",
        ["じゃがいも", "にんじん", "きゅうり"],
    ),
    (
        "ラタトゥイユ",
        "野菜料理",
        ["トマト", "玉ねぎ", "なす", "ズッキーニ", "パプリカ"],
    ),
    (
        "さつまいもおやき",
        "野菜料理",
        ["さつまいも", "米粉"],
    ),
    (
        "野菜おやき",
        "野菜料理",
        ["じゃがいも", "にんじん", "キャベツ", "米粉"],
    ),

    # 魚料理
    (
        "白身魚の野菜煮",
        "魚料理",
        ["たら", "にんじん", "玉ねぎ", "ブロッコリー"],
    ),
    (
        "鮭のクリーム煮",
        "魚料理",
        ["さけ", "牛乳", "玉ねぎ", "ブロッコリー"],
    ),
    (
        "しらすと野菜の煮物",
        "魚料理",
        ["しらす", "にんじん", "大根", "小松菜"],
    ),
    (
        "ツナとじゃがいもの煮物",
        "魚料理",
        ["ツナ（水煮）", "じゃがいも", "玉ねぎ"],
    ),
    (
        "白身魚のつみれ",
        "魚料理",
        ["たら", "豆腐", "玉ねぎ"],
    ),

    # 肉料理
    (
        "鶏そぼろ",
        "肉料理",
        ["鶏肉"],
    ),
    (
        "鶏肉と野菜の煮物",
        "肉料理",
        ["鶏肉", "にんじん", "玉ねぎ", "じゃがいも"],
    ),
    (
        "肉じゃが",
        "肉料理",
        ["牛肉", "じゃがいも", "にんじん", "玉ねぎ"],
    ),
    (
        "豆腐ハンバーグ",
        "肉料理",
        ["豆腐", "鶏肉", "玉ねぎ", "にんじん"],
    ),
    (
        "ミートボール",
        "肉料理",
        ["豚肉", "玉ねぎ", "にんじん"],
    ),
    (
        "鶏肉のトマト煮",
        "肉料理",
        ["鶏肉", "トマト", "玉ねぎ", "にんじん"],
    ),

    # 卵料理
    (
        "卵とじ",
        "卵料理",
        ["全卵", "玉ねぎ", "にんじん", "かつおだし"],
    ),
    (
        "オムレツ",
        "卵料理",
        ["全卵", "牛乳", "にんじん", "ほうれん草"],
    ),
    (
        "卵焼き",
        "卵料理",
        ["全卵"],
    ),
    (
        "茶碗蒸し",
        "卵料理",
        ["全卵", "鶏肉", "にんじん", "しいたけ", "かつおだし"],
    ),

    # 豆腐・大豆料理
    (
        "豆腐の野菜あんかけ",
        "豆腐・大豆料理",
        ["豆腐", "にんじん", "玉ねぎ", "小松菜"],
    ),
    (
        "白和え",
        "豆腐・大豆料理",
        ["豆腐", "ほうれん草", "にんじん"],
    ),
    (
        "高野豆腐の煮物",
        "豆腐・大豆料理",
        ["高野豆腐", "にんじん", "しいたけ", "かつおだし"],
    ),
    (
        "納豆と野菜の和え物",
        "豆腐・大豆料理",
        ["納豆", "小松菜", "にんじん"],
    ),

    # スープ・汁物
    (
        "野菜スープ",
        "スープ・汁物",
        ["にんじん", "玉ねぎ", "キャベツ"],
    ),
    (
        "コーンスープ",
        "スープ・汁物",
        ["とうもろこし", "牛乳"],
    ),
    (
        "かぼちゃスープ",
        "スープ・汁物",
        ["かぼちゃ", "玉ねぎ", "牛乳"],
    ),
    (
        "ミネストローネ",
        "スープ・汁物",
        ["トマト", "にんじん", "玉ねぎ", "キャベツ", "じゃがいも"],
    ),
    (
        "味噌汁",
        "スープ・汁物",
        ["味噌", "豆腐", "わかめ", "大根"],
    ),
    (
        "鶏肉と野菜のスープ",
        "スープ・汁物",
        ["鶏肉", "にんじん", "玉ねぎ", "キャベツ"],
    ),

    # 果物・デザート
    (
        "バナナヨーグルト",
        "果物・デザート",
        ["バナナ", "プレーンヨーグルト"],
    ),
    (
        "りんごヨーグルト",
        "果物・デザート",
        ["りんご", "プレーンヨーグルト"],
    ),
    (
        "フルーツヨーグルト",
        "果物・デザート",
        ["バナナ", "りんご", "プレーンヨーグルト"],
    ),
    (
        "さつまいもヨーグルト",
        "果物・デザート",
        ["さつまいも", "プレーンヨーグルト"],
    ),
    (
        "りんごのコンポート",
        "果物・デザート",
        ["りんご"],
    ),
    (
        "りんごとバナナのペースト",
        "果物・デザート",
        ["りんご", "バナナ"],
    ),
]

# 1食あたりの目安量
#
# タプルの構造：
# (
#   開始月齢,
#   終了月齢,
#   食品群コード,
#   最小量,
#   最大量,
#   単位,
#   食品形態・補足,
#   表示用注記,
#   表示順,
# )
FEEDING_GUIDELINES = [
    # 7〜8か月
    (
        7,
        8,
        FeedingGroup.Code.GRAIN,
        50,
        80,
        FeedingGuideline.Unit.GRAM,
        "全がゆ",
        "",
        10,
    ),
    (
        7,
        8,
        FeedingGroup.Code.VEGETABLE_FRUIT,
        20,
        30,
        FeedingGuideline.Unit.GRAM,
        "",
        "",
        20,
    ),
    (
        7,
        8,
        FeedingGroup.Code.FISH,
        10,
        15,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        30,
    ),
    (
        7,
        8,
        FeedingGroup.Code.MEAT,
        10,
        15,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        40,
    ),
    (
        7,
        8,
        FeedingGroup.Code.TOFU,
        30,
        40,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        50,
    ),
    (
        7,
        8,
        FeedingGroup.Code.EGG,
        0.33,
        1,
        FeedingGuideline.Unit.EGG,
        "卵黄1個〜全卵1/3個",
        "数値バーではなく注記として表示",
        60,
    ),
    (
        7,
        8,
        FeedingGroup.Code.DAIRY,
        50,
        70,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        70,
    ),

    # 9〜11か月
    (
        9,
        11,
        FeedingGroup.Code.GRAIN,
        80,
        90,
        FeedingGuideline.Unit.GRAM,
        "全がゆ90g〜軟飯80g",
        "",
        10,
    ),
    (
        9,
        11,
        FeedingGroup.Code.VEGETABLE_FRUIT,
        30,
        40,
        FeedingGuideline.Unit.GRAM,
        "",
        "",
        20,
    ),
    (
        9,
        11,
        FeedingGroup.Code.FISH,
        15,
        15,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        30,
    ),
    (
        9,
        11,
        FeedingGroup.Code.MEAT,
        15,
        15,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        40,
    ),
    (
        9,
        11,
        FeedingGroup.Code.TOFU,
        45,
        45,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        50,
    ),
    (
        9,
        11,
        FeedingGroup.Code.EGG,
        0.5,
        0.5,
        FeedingGuideline.Unit.EGG,
        "全卵1/2個",
        "数値バーではなく注記として表示",
        60,
    ),
    (
        9,
        11,
        FeedingGroup.Code.DAIRY,
        80,
        80,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        70,
    ),

    # 12〜18か月
    (
        12,
        18,
        FeedingGroup.Code.GRAIN,
        80,
        90,
        FeedingGuideline.Unit.GRAM,
        "軟飯90g〜ご飯80g",
        "",
        10,
    ),
    (
        12,
        18,
        FeedingGroup.Code.VEGETABLE_FRUIT,
        40,
        50,
        FeedingGuideline.Unit.GRAM,
        "",
        "",
        20,
    ),
    (
        12,
        18,
        FeedingGroup.Code.FISH,
        15,
        20,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        30,
    ),
    (
        12,
        18,
        FeedingGroup.Code.MEAT,
        15,
        20,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        40,
    ),
    (
        12,
        18,
        FeedingGroup.Code.TOFU,
        50,
        55,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        50,
    ),
    (
        12,
        18,
        FeedingGroup.Code.EGG,
        0.5,
        0.67,
        FeedingGuideline.Unit.EGG,
        "全卵1/2〜2/3個",
        "数値バーではなく注記として表示",
        60,
    ),
    (
        12,
        18,
        FeedingGroup.Code.DAIRY,
        100,
        100,
        FeedingGuideline.Unit.GRAM,
        "",
        "いずれか1種類が目安",
        70,
    ),
]

FOOD_FEEDING_GROUP_MAP = {
    # 穀類
    "米": FeedingGroup.Code.GRAIN,
    "米粉": FeedingGroup.Code.GRAIN,
    "オートミール": FeedingGroup.Code.GRAIN,
    "小麦粉": FeedingGroup.Code.GRAIN,
    "食パン": FeedingGroup.Code.GRAIN,
    "うどん": FeedingGroup.Code.GRAIN,
    "そうめん": FeedingGroup.Code.GRAIN,
    "パスタ": FeedingGroup.Code.GRAIN,
    "マカロニ": FeedingGroup.Code.GRAIN,
    "そば": FeedingGroup.Code.GRAIN,

    # 野菜・果物
    "にんじん": FeedingGroup.Code.VEGETABLE_FRUIT,
    "かぼちゃ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "大根": FeedingGroup.Code.VEGETABLE_FRUIT,
    "かぶ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "玉ねぎ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "トマト": FeedingGroup.Code.VEGETABLE_FRUIT,
    "キャベツ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "白菜": FeedingGroup.Code.VEGETABLE_FRUIT,
    "ブロッコリー": FeedingGroup.Code.VEGETABLE_FRUIT,
    "カリフラワー": FeedingGroup.Code.VEGETABLE_FRUIT,
    "ほうれん草": FeedingGroup.Code.VEGETABLE_FRUIT,
    "小松菜": FeedingGroup.Code.VEGETABLE_FRUIT,
    "チンゲン菜": FeedingGroup.Code.VEGETABLE_FRUIT,
    "レタス": FeedingGroup.Code.VEGETABLE_FRUIT,
    "きゅうり": FeedingGroup.Code.VEGETABLE_FRUIT,
    "なす": FeedingGroup.Code.VEGETABLE_FRUIT,
    "ズッキーニ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "ピーマン": FeedingGroup.Code.VEGETABLE_FRUIT,
    "パプリカ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "とうもろこし": FeedingGroup.Code.VEGETABLE_FRUIT,
    "アスパラガス": FeedingGroup.Code.VEGETABLE_FRUIT,
    "オクラ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "ごぼう": FeedingGroup.Code.VEGETABLE_FRUIT,
    "れんこん": FeedingGroup.Code.VEGETABLE_FRUIT,
    "もやし": FeedingGroup.Code.VEGETABLE_FRUIT,
    "じゃがいも": FeedingGroup.Code.VEGETABLE_FRUIT,
    "さつまいも": FeedingGroup.Code.VEGETABLE_FRUIT,
    "里芋": FeedingGroup.Code.VEGETABLE_FRUIT,
    "長芋": FeedingGroup.Code.VEGETABLE_FRUIT,
    "山芋": FeedingGroup.Code.VEGETABLE_FRUIT,
    "りんご": FeedingGroup.Code.VEGETABLE_FRUIT,
    "バナナ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "もも": FeedingGroup.Code.VEGETABLE_FRUIT,
    "オレンジ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "みかん": FeedingGroup.Code.VEGETABLE_FRUIT,
    "キウイフルーツ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "いちご": FeedingGroup.Code.VEGETABLE_FRUIT,
    "なし": FeedingGroup.Code.VEGETABLE_FRUIT,
    "ぶどう": FeedingGroup.Code.VEGETABLE_FRUIT,
    "スイカ": FeedingGroup.Code.VEGETABLE_FRUIT,
    "メロン": FeedingGroup.Code.VEGETABLE_FRUIT,
    "柿": FeedingGroup.Code.VEGETABLE_FRUIT,
    "パイナップル": FeedingGroup.Code.VEGETABLE_FRUIT,
    "マンゴー": FeedingGroup.Code.VEGETABLE_FRUIT,
    "ブルーベリー": FeedingGroup.Code.VEGETABLE_FRUIT,
    "プルーン": FeedingGroup.Code.VEGETABLE_FRUIT,
    "アボカド": FeedingGroup.Code.VEGETABLE_FRUIT,

    # 魚
    "たい": FeedingGroup.Code.FISH,
    "ひらめ": FeedingGroup.Code.FISH,
    "かれい": FeedingGroup.Code.FISH,
    "たら": FeedingGroup.Code.FISH,
    "さけ": FeedingGroup.Code.FISH,
    "まぐろ": FeedingGroup.Code.FISH,
    "かつお": FeedingGroup.Code.FISH,
    "ぶり": FeedingGroup.Code.FISH,
    "いわし": FeedingGroup.Code.FISH,
    "あじ": FeedingGroup.Code.FISH,
    "さば": FeedingGroup.Code.FISH,
    "しらす": FeedingGroup.Code.FISH,
    "ツナ（水煮）": FeedingGroup.Code.FISH,

    # 肉
    "鶏肉": FeedingGroup.Code.MEAT,
    "鶏レバー": FeedingGroup.Code.MEAT,
    "牛肉": FeedingGroup.Code.MEAT,
    "豚肉": FeedingGroup.Code.MEAT,

    # 豆腐
    "豆腐": FeedingGroup.Code.TOFU,
    "高野豆腐": FeedingGroup.Code.TOFU,

    # 卵
    "卵黄": FeedingGroup.Code.EGG,
    "卵白": FeedingGroup.Code.EGG,
    "全卵": FeedingGroup.Code.EGG,

    # 乳製品
    "牛乳": FeedingGroup.Code.DAIRY,
    "プレーンヨーグルト": FeedingGroup.Code.DAIRY,
    "カッテージチーズ": FeedingGroup.Code.DAIRY,
    "粉チーズ": FeedingGroup.Code.DAIRY,
}

class Command(BaseCommand):
    help = "ジャンル、アレルゲン、基本食材の初期データを登録します。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="既存の初期データもコードの内容で上書きします。",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force"]

        food_category_counts = self.seed_categories(
            FoodCategory,
            FOOD_CATEGORIES,
            force,
        )

        dish_category_counts = self.seed_categories(
            DishCategory,
            DISH_CATEGORIES,
            force,
        )

        feeding_group_counts = self.seed_feeding_groups(force)
        allergen_counts = self.seed_allergens(force)
        food_counts = self.seed_foods(force)
        food_group_counts = self.assign_food_feeding_groups(force)
        guideline_counts = self.seed_feeding_guidelines(force)
        dish_counts = self.seed_dishes(force)

        self.stdout.write(
            self.style.SUCCESS(
                "\nマスターデータの登録が完了しました。\n"
                f"食材ジャンル："
                f"{self.format_counts(food_category_counts)}\n"
                f"料理ジャンル："
                f"{self.format_counts(dish_category_counts)}\n"
                f"標準量用食品群："
                f"{self.format_counts(feeding_group_counts)}\n"
                f"アレルゲン："
                f"{self.format_counts(allergen_counts)}\n"
                f"食材："
                f"{self.format_counts(food_counts)}\n"
                f"食材の食品群設定："
                f"{self.format_counts(food_group_counts)}\n"
                f"月齢別標準量："
                f"{self.format_counts(guideline_counts)}\n"
                f"料理："
                f"{self.format_counts(dish_counts)}"
            )
        )

        if not force:
            self.stdout.write(
                "\n既存データは変更していません。"
                "\nコードの内容で既存データも更新する場合は、"
                "\npython manage.py seed_master_data --force"
                "\nを実行してください。"
            )

    def seed_categories(self, model, category_data, force):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for name, display_order in category_data:
            category = model.objects.filter(name=name).first()

            if category is None:
                model.objects.create(
                    name=name,
                    display_order=display_order,
                    is_active=True,
                )
                created_count += 1
                continue

            if force:
                category.display_order = display_order
                category.is_active = True
                category.save()
                updated_count += 1
            else:
                skipped_count += 1

        return created_count, updated_count, skipped_count

    def seed_allergens(self, force):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for name, classification, display_order in ALLERGENS:
            allergen = Allergen.objects.filter(name=name).first()

            if allergen is None:
                Allergen.objects.create(
                    name=name,
                    classification=classification,
                    display_order=display_order,
                    is_active=True,
                )
                created_count += 1
                continue

            if force:
                allergen.classification = classification
                allergen.display_order = display_order
                allergen.is_active = True
                allergen.save()
                updated_count += 1
            else:
                skipped_count += 1

        return created_count, updated_count, skipped_count

    def seed_foods(self, force):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        categories = {
            category.name: category
            for category in FoodCategory.objects.all()
        }

        allergens = {
            allergen.name: allergen
            for allergen in Allergen.objects.all()
        }

        for (
            food_name,
            category_name,
            allergen_names,
            show_in_first_year_list,
        ) in FOODS:
            category = categories[category_name]

            food = Food.objects.filter(name=food_name).first()

            if food is None:
                food = Food.objects.create(
                    name=food_name,
                    category=category,
                    is_user_created=False,
                    show_in_first_year_list=show_in_first_year_list,
                    is_active=True,
                )

                food.allergens.set(
                    [allergens[name] for name in allergen_names]
                )

                created_count += 1
                continue

            if force:
                food.category = category
                food.is_user_created = False
                food.show_in_first_year_list = show_in_first_year_list
                food.is_active = True
                food.save()

                food.allergens.set(
                    [allergens[name] for name in allergen_names]
                )

                updated_count += 1
            else:
                skipped_count += 1

        return created_count, updated_count, skipped_count

    def seed_dishes(self, force):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        categories = {
            category.name: category
            for category in DishCategory.objects.all()
        }

        foods = {
            food.name: food
            for food in Food.objects.all()
        }

        for dish_name, category_name, ingredient_names in DISHES:
            if category_name not in categories:
                raise CommandError(
                    f"料理ジャンル「{category_name}」が登録されていません。"
                )

            missing_foods = [
                name
                for name in ingredient_names
                if name not in foods
            ]

            if missing_foods:
                missing_names = "、".join(missing_foods)

                raise CommandError(
                    f"料理「{dish_name}」の材料が登録されていません："
                    f"{missing_names}"
                )

            category = categories[category_name]
            dish = Dish.objects.filter(name=dish_name).first()

            if dish is None:
                dish = Dish.objects.create(
                    name=dish_name,
                    category=category,
                    is_user_created=False,
                    is_active=True,
                )

                self.replace_dish_ingredients(
                    dish=dish,
                    ingredient_names=ingredient_names,
                    foods=foods,
                )

                created_count += 1
                continue

            if force:
                dish.category = category
                dish.is_user_created = False
                dish.is_active = True
                dish.save()

                self.replace_dish_ingredients(
                    dish=dish,
                    ingredient_names=ingredient_names,
                    foods=foods,
                )

                updated_count += 1
            else:
                skipped_count += 1

        return created_count, updated_count, skipped_count

    @staticmethod
    def replace_dish_ingredients(
        dish,
        ingredient_names,
        foods,
    ):
        DishIngredient.objects.filter(dish=dish).delete()

        dish_ingredients = [
            DishIngredient(
                dish=dish,
                food=foods[food_name],
                display_order=index * 10,
            )
            for index, food_name in enumerate(
                ingredient_names,
                start=1,
            )
        ]

        DishIngredient.objects.bulk_create(dish_ingredients)

    def seed_feeding_groups(self, force):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for code, name, display_order in FEEDING_GROUPS:
            group = FeedingGroup.objects.filter(
                code=code
            ).first()

            if group is None:
                FeedingGroup.objects.create(
                    code=code,
                    name=name,
                    display_order=display_order,
                    is_active=True,
                )
                created_count += 1
                continue

            if force:
                group.name = name
                group.display_order = display_order
                group.is_active = True
                group.save()
                updated_count += 1
            else:
                skipped_count += 1

        return (
            created_count,
            updated_count,
            skipped_count,
        )

    def seed_feeding_guidelines(self, force):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        groups = {
            group.code: group
            for group in FeedingGroup.objects.all()
        }

        for (
            min_age,
            max_age,
            group_code,
            minimum,
            maximum,
            unit,
            food_form_note,
            display_note,
            display_order,
        ) in FEEDING_GUIDELINES:
            guideline = FeedingGuideline.objects.filter(
                min_age_months=min_age,
                max_age_months=max_age,
                feeding_group=groups[group_code],
            ).first()

            values = {
                "minimum_amount": minimum,
                "maximum_amount": maximum,
                "unit": unit,
                "food_form_note": food_form_note,
                "display_note": display_note,
                "display_order": display_order,
            }

            if guideline is None:
                FeedingGuideline.objects.create(
                    min_age_months=min_age,
                    max_age_months=max_age,
                    feeding_group=groups[group_code],
                    **values,
                )
                created_count += 1
                continue

            if force:
                for field_name, value in values.items():
                    setattr(
                        guideline,
                        field_name,
                        value,
                    )

                guideline.save()
                updated_count += 1
            else:
                skipped_count += 1

        return (
            created_count,
            updated_count,
            skipped_count,
        )

    def assign_food_feeding_groups(self, force):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        groups = {
            group.code: group
            for group in FeedingGroup.objects.all()
        }

        for food in Food.objects.all():
            group_code = FOOD_FEEDING_GROUP_MAP.get(
                food.name,
                FeedingGroup.Code.OTHER,
            )

            selected_group = groups[group_code]

            if food.feeding_group_id == selected_group.id:
                skipped_count += 1
                continue

            if food.feeding_group_id is None or force:
                food.feeding_group = selected_group
                food.save(
                    update_fields=[
                        "feeding_group",
                        "updated_at",
                    ]
                )
                updated_count += 1
            else:
                skipped_count += 1

        return (
            created_count,
            updated_count,
            skipped_count,
        )

    @staticmethod
    def format_counts(counts):
        created, updated, skipped = counts

        return (
            f"新規 {created}件、"
            f"更新 {updated}件、"
            f"変更なし {skipped}件"
        )