"""興味のある分野: tag events, trips and places by what they offer.

The data has no shared genre field, so each item is tagged from its event
category / place kind and from words in its Japanese (and original) text.
Used to rank HOME and さがす for the visitor's interests and to filter さがす.
"""

INTERESTS = [
    ("hiking", "ハイキング", "🥾"),
    ("view", "絶景・山", "🏔️"),
    ("ski", "スキー・雪", "⛷️"),
    ("lake", "湖・船", "⛵"),
    ("food", "グルメ", "🧀"),
    ("heritage", "世界遺産・歴史", "🏰"),
    ("architecture", "建築", "🏛️"),
    ("art", "アート・博物館", "🎨"),
    ("music", "音楽・お祭り", "🎶"),
    ("sports", "スポーツ", "🚴"),
    ("animals", "動物・自然", "🐄"),
    ("wellness", "温泉・スパ", "♨️"),
]
KEYS = [key for key, _, _ in INTERESTS]
LABELS = {key: f"{emoji} {label}" for key, label, emoji in INTERESTS}

# Words in the text (Japanese first; a few German/English for untranslated titles).
WORDS = {
    "hiking": ["ハイキング", "ハイク", "トレッキング", "山歩き", "散策路", "遊歩道", "ウォーキング", "トレイル",
               "wanderung", "wanderweg", "hike", "hiking", "trail"],
    "view": ["絶景", "展望", "パノラマ", "眺望", "見晴らし", "山頂", "ロープウェイ", "ゴンドラ", "登山鉄道", "氷河",
             "panorama", "aussicht", "gipfel", "gletscher", "seilbahn"],
    "ski": ["スキー", "スノーボード", "ソリ", "そり", "スノーシュー", "雪遊び", "ski", "schlitten", "snowboard"],
    "lake": ["湖", "クルーズ", "遊覧船", "船で", "ボート", "schiff", "see ", "lake", "bootsfahrt"],
    "food": ["グルメ", "料理", "レストラン", "チーズ", "チョコレート", "ワイン", "ビール", "フォンデュ", "ラクレット",
             "食べ歩き", "マルシェ", "試食", "käse", "schokolade", "wein", "fondue", "raclette", "kulinar"],
    "heritage": ["世界遺産", "ユネスコ", "城", "修道院", "旧市街", "歴史的", "中世", "遺跡", "unesco", "schloss", "burg", "kloster", "altstadt"],
    "architecture": ["建築", "大聖堂", "教会", "聖堂", "建築家", "architektur", "kathedrale", "münster"],
    "art": ["美術", "アート", "博物館", "美術館", "ミュージアム", "ギャラリー", "展示", "museum", "kunst", "galerie", "ausstellung"],
    "music": ["音楽", "コンサート", "ライブ", "祭り", "フェスティバル", "パレード", "カーニバル", "クリスマスマーケット",
              "konzert", "festival", "fasnacht", "weihnachtsmarkt"],
    "sports": ["スポーツ", "自転車", "サイクリング", "マウンテンバイク", "カヤック", "パラグライ", "クライミング",
               "ゴルフ", "ラフティング", "スケート", "velo", "bike", "klettern", "rafting"],
    "animals": ["動物", "動物園", "野生", "牧場", "農場", "zoo", "tierpark", "wildpark", "bauernhof"],
    "wellness": ["温泉", "スパ", "サウナ", "テルメ", "ウェルネス", "therme", "wellness", "sauna"],
}

EVENT_CATEGORIES = {
    "food": ["food"], "market": ["food"], "art": ["art"], "museum": ["art"], "theater": ["art"], "film": ["art"],
    "music": ["music"], "festival": ["music"], "seasonal": ["music"], "nature": ["hiking", "animals"],
    "sports": ["sports"], "tour": ["heritage"],
}
KIDS_KINDS = {
    "animals": ["animals"], "farm": ["animals", "food"], "museum": ["art"], "nature": ["hiking", "animals"],
    "mountain": ["view"], "water": ["lake"], "history": ["heritage"],
}
TRIP_TYPES = {"tours": ["hiking"]}


def tag(text, *, category="", kind="", spot_type=""):
    """The interest keys an item matches."""
    found = set(EVENT_CATEGORIES.get(category, [])) | set(KIDS_KINDS.get(kind, [])) | set(TRIP_TYPES.get(spot_type, []))
    lowered = (text or "").lower()
    for key, words in WORDS.items():
        if key not in found and any(word.lower() in lowered for word in words):
            found.add(key)
    return found


def clean(values):
    return [v for v in dict.fromkeys(values) if v in KEYS]
