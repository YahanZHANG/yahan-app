import re


# =========================================================
# Main regions
# =========================================================

REGION_ALIASES = {

    "zurich": [
        "zürich",
        "zurich",
        "zuerich",
        "zürichsee",
        "zurichsee",
        "dietikon",
        "uster",
        "wetzikon",
        "horgen",
        "meilen",
        "bülach",
        "buelach",
        "dübendorf",
        "duebendorf",
        "effretikon",
        "rüti",
        "rueti",

        # Japanese
        "チューリヒ",
        "チューリッヒ",
        "チューリヒ州",
        "チューリヒ市",
        "チューリヒ湖",
        "デューベンドルフ",
        "エフレティコン",
        "リューティ",
    ],

    "winterthur": [
        "winterthur",

        # Japanese
        "ヴィンタートゥール",
        "ウィンタートゥール",
        "ヴィンタートゥア",
    ],

    "geneva": [
        "genève",
        "geneve",
        "geneva",
        "genf",

        # Japanese
        "ジュネーブ",
        "ジュネーヴ",
        "ジュネーブ州",
        "ジュネーヴ州",
    ],

    "basel": [
        "basel",
        "basel-stadt",
        "basel stadt",
        "basel-landschaft",
        "basel landschaft",
        "baselland",
        "liestal",
        "pratteln",

        # Japanese
        "バーゼル",
        "バーゼル州",
        "バーゼル市",
        "バーゼル＝シュタット",
        "バーゼル・シュタット",
        "バーゼル＝ラント",
        "バーゼル・ラント",
        "プラッテルン",
        "リースタル",
    ],

    "lausanne-vaud": [
        "lausanne",
        "vaud",
        "waadt",
        "vevey",
        "montreux",
        "nyon",
        "yverdon",
        "morges",

        # Japanese
        "ローザンヌ",
        "ローザンヌ市",
        "ヴォー州",
        "ヴォー",
        "ヴェヴェイ",
        "モントルー",
        "ニヨン",
        "イヴェルドン",
        "モルジュ",
        "EPFL",
    ],

    "bern": [
        "bern",
        "berne",
        "berner",
        "emmental",
        "oberland bernois",
        "interlaken",
        "ostermundigen",

        # Japanese
        "ベルン",
        "ベルン州",
        "ベルン市",
        "ベルナーオーバーラント",
        "インターラーケン",
        "オスタームンディゲン",
    ],

    "lucerne": [
        "luzern",
        "lucerne",
        "lucerna",
        "kriens",

        # Japanese
        "ルツェルン",
        "ルツェルン州",
        "ルツェルン市",
        "クリエンス",
    ],

    "st-gallen": [
        "st. gallen",
        "st.gallen",
        "st gallen",
        "saint-gall",
        "sankt gallen",
        "wittenbach",

        # Japanese
        "ザンクト・ガレン",
        "ザンクトガレン",
        "ザンクト・ガレン州",
        "サン・ガレン",
        "サン＝ガレン",
        "ヴィッテンバッハ",
    ],

    "lugano-ticino": [
        "lugano",
        "ticino",
        "tessin",
        "locarno",
        "bellinzona",
        "mendrisio",
        "chiasso",
        "verzasca",

        # Japanese
        "ルガーノ",
        "ティチーノ",
        "ティチーノ州",
        "テッシン",
        "ロカルノ",
        "ベリンツォーナ",
        "ベリンツォナ",
        "メンドリジオ",
        "キアッソ",
        "ヴェルザスカ",
    ],

    "zug": [
        "zug",
        "zoug",

        # Japanese
        "ツーク",
        "ツーク州",
        "ツーク市",
    ],

    "biel-bienne": [
        "biel",
        "bienne",
        "biel/bienne",

        # Japanese
        "ビール",
        "ビエンヌ",
        "ビール／ビエンヌ",
        "ビール・ビエンヌ",
    ],

    "fribourg": [
        "fribourg",
        "freiburg",

        # Japanese
        "フリブール",
        "フリブール州",
        "フライブルク",
    ],

    "neuchatel": [
        "neuchâtel",
        "neuchatel",
        "neuenburg",

        # Japanese
        "ヌーシャテル",
        "ヌシャテル",
        "ヌーシャテル州",
        "ヌシャテル州",
    ],

    "thun": [
        "thun",
        "thoune",

        # Japanese
        "トゥーン",
        "トゥン",
    ],

    "chur-graubuenden": [
        "chur",
        "coire",
        "graubünden",
        "graubuenden",
        "grisons",
        "grigioni",
        "davos",
        "st. moritz",
        "st moritz",

        # Japanese
        "クール",
        "グラウビュンデン",
        "グラウビュンデン州",
        "グリゾン",
        "ダボス",
        "サンモリッツ",
        "サン・モリッツ",
    ],

    "sion-valais": [
        "sion",
        "valais",
        "wallis",
        "martigny",
        "brig",
        "visp",
        "zermatt",
        "simplon",

        # Japanese
        "シオン",
        "ヴァレー",
        "ヴァレー州",
        "ヴァリス",
        "マルティニー",
        "ブリーク",
        "フィスプ",
        "ツェルマット",
        "シンプロン",
    ],

    "aarau-aargau": [
        "aarau",
        "aargau",
        "argovie",
        "baden",
        "wettingen",
        "würenlos",
        "wuerenlos",

        # Japanese
        "アーラウ",
        "アールガウ",
        "アールガウ州",
        "バーデン",
        "ヴェッティンゲン",
        "ヴューレンロース",
    ],

    "schaffhausen": [
        "schaffhausen",
        "schaffhouse",

        # Japanese
        "シャフハウゼン",
        "シャフハウゼン州",
    ],

    "solothurn": [
        "solothurn",
        "soleure",
        "olten",
        "grenchen",

        # Japanese
        "ゾロトゥルン",
        "ゾロトゥルン州",
        "オルテン",
        "グレンヘン",
    ],

}


# =========================================================
# Other Swiss regions
# =========================================================

OTHER_SWISS_ALIASES = [

    # Uri
    "uri",
    "altdorf",
    "ウリ州",
    "ウリ",
    "アルトドルフ",

    # Schwyz
    "schwyz",
    "einsiedeln",
    "pfäffikon",
    "pfaeffikon",
    "シュヴィーツ",
    "シュヴィーツ州",
    "アインジーデルン",
    "プフェフィコン",

    # Obwalden
    "obwalden",
    "sarnen",
    "alpnach",
    "オプヴァルデン",
    "オプヴァルデン州",
    "ザルネン",
    "アルプナッハ",

    # Nidwalden
    "nidwalden",
    "stans",
    "ニトヴァルデン",
    "ニトヴァルデン州",
    "シュタンス",

    # Glarus
    "glarus",
    "glarner",
    "elm",
    "グラールス",
    "グラールス州",
    "エルム",

    # Appenzell
    "appenzell",
    "herisau",
    "アッペンツェル",
    "ヘリザウ",

    # Thurgau
    "thurgau",
    "thurgovie",
    "frauenfeld",
    "kreuzlingen",
    "トゥールガウ",
    "トゥールガウ州",
    "フラウエンフェルト",
    "クロイツリンゲン",

    # Jura
    "jura",
    "delémont",
    "delemont",
    "ジュラ州",
    "ジュラ",
    "ドレモン",
    "デルベルク",

]


# =========================================================
# Strong national-level signals
#
# These should strongly indicate Switzerland-wide news
# when they occur in the TITLE.
# =========================================================

NATIONAL_TITLE_ALIASES = [

    # Japanese
    "スイス",
    "スイス国民",
    "国民投票",
    "国民発議",
    "連邦参事会",
    "連邦参事",
    "連邦議会",
    "国民議会",
    "全州議会",
    "連邦裁判所",
    "連邦政府",
    "スイス軍",
    "スイス国立銀行",
    "国防相",
    "連邦事務総長",
    "連邦当局",

    # German
    "schweiz",
    "schweizer",
    "schweizerisch",
    "bundesrat",
    "bundesversammlung",
    "nationalrat",
    "ständerat",
    "staenderat",
    "bundesgericht",
    "eidgenössische volksabstimmung",
    "eidgenoessische volksabstimmung",

    # French
    "suisse",
    "conseil fédéral",
    "conseil federal",
    "confédération",
    "confederation",
    "conseil national",
    "conseil des états",
    "conseil des etats",

    # Italian
    "svizzera",
    "consiglio federale",
    "confederazione",
    "consiglio nazionale",

    # English
    "switzerland",
    "swiss federal",
    "federal council",
    "federal parliament",
]


# =========================================================
# Weaker national signals
#
# Summary alone may contain these incidentally.
# Therefore they are only used as fallback signals.
# =========================================================

NATIONAL_SUMMARY_ALIASES = [

    "bundesrat",
    "bundesversammlung",
    "nationalrat",
    "ständerat",
    "staenderat",
    "bundesgericht",

    "conseil fédéral",
    "conseil federal",
    "conseil national",

    "consiglio federale",

    "federal council",
    "federal parliament",

    "連邦参事会",
    "連邦議会",
    "国民議会",
    "全州議会",
    "連邦裁判所",
    "スイス軍",
    "スイス国立銀行",
]


# =========================================================
# Helpers
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    text = text.lower()

    text = text.replace(
        "　",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def contains_alias(
    text,
    alias,
):

    if not text or not alias:
        return False

    text = normalize_text(
        text
    )

    alias = normalize_text(
        alias
    )

    pattern = (
        r"(?<!\w)"
        + re.escape(alias)
        + r"(?!\w)"
    )

    return bool(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
    )


def matching_region_slugs(
    text,
):

    matched_slugs = []

    for slug, aliases in REGION_ALIASES.items():

        if any(
            contains_alias(
                text,
                alias,
            )
            for alias in aliases
        ):

            matched_slugs.append(
                slug
            )

    return list(
        dict.fromkeys(
            matched_slugs
        )
    )


def contains_other_swiss_region(
    text,
):

    return any(
        contains_alias(
            text,
            alias,
        )
        for alias in OTHER_SWISS_ALIASES
    )


def contains_national_title_signal(
    text,
):

    return any(
        contains_alias(
            text,
            alias,
        )
        for alias in NATIONAL_TITLE_ALIASES
    )


def contains_national_summary_signal(
    text,
):

    return any(
        contains_alias(
            text,
            alias,
        )
        for alias in NATIONAL_SUMMARY_ALIASES
    )


# =========================================================
# Main classifier
# =========================================================

def classify_region_slugs(article):

    """
    Return candidate Region.slug values.

    Priority:

    1. Explicit main region in title
    2. Explicit other Swiss region in title
    3. National-level signal in title
    4. Strong regional evidence in summary
    5. Strong national evidence in summary
    6. Unknown

    Important:
    Summary text is deliberately treated as weaker evidence
    because news summaries often mention Bern, Zürich, etc.
    incidentally.
    """

    # =====================================================
    # Separate title and summary
    # =====================================================

    title_text = normalize_text(
        " ".join([
            article.title_original or "",
            article.title_ja or "",
        ])
    )

    summary_text = normalize_text(
        " ".join([
            article.summary_original or "",
            article.summary_ja or "",
        ])
    )

    # =====================================================
    # 1. Explicit main region in TITLE
    # =====================================================

    title_regions = matching_region_slugs(
        title_text
    )

    if title_regions:

        return title_regions

    # =====================================================
    # 2. Other Swiss region in TITLE
    # =====================================================

    if contains_other_swiss_region(
        title_text
    ):

        return [
            "other"
        ]

    # =====================================================
    # 3. Switzerland-wide signal in TITLE
    # =====================================================

    if contains_national_title_signal(
        title_text
    ):

        return [
            "switzerland"
        ]

    # =====================================================
    # 4. Regional fallback from SUMMARY
    #
    # Summary is intentionally conservative.
    #
    # Only assign a region when:
    # - exactly one region is found
    # - and there is no strong national signal
    #
    # This prevents things such as:
    # federal article + "Bern" dateline
    # being incorrectly classified as Bern.
    # =====================================================

    summary_regions = matching_region_slugs(
        summary_text
    )

    summary_is_national = (
        contains_national_summary_signal(
            summary_text
        )
    )

    if (
        len(summary_regions) == 1
        and not summary_is_national
    ):

        return summary_regions

    # =====================================================
    # 5. Other Swiss region in SUMMARY
    # =====================================================

    if (
        contains_other_swiss_region(
            summary_text
        )
        and not summary_is_national
    ):

        return [
            "other"
        ]

    # =====================================================
    # 6. National fallback from SUMMARY
    # =====================================================

    if summary_is_national:

        return [
            "switzerland"
        ]

    # =====================================================
    # 7. Unknown
    # =====================================================

    return [
        "unknown"
    ]