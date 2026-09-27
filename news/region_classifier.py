import re


# =========================================================
# Region aliases
# =========================================================

REGION_ALIASES = {

    "zurich": [
        "zürich",
        "zurich",
        "zuerich",
        "dietikon",
        "uster",
        "wetzikon",
        "horgen",
        "meilen",
        "bülach",
        "buelach",
    ],

    "winterthur": [
        "winterthur",
    ],

    "geneva": [
        "genève",
        "geneve",
        "geneva",
        "genf",
    ],

    "basel": [
        "basel",
        "basel-stadt",
        "basel-landschaft",
        "baselland",
        "liestal",
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
    ],

    "bern": [
        "bern",
        "berne",
        "berner",
        "emmental",
        "oberland bernois",
    ],

    "lucerne": [
        "luzern",
        "lucerne",
        "lucerna",
    ],

    "winterthur": [
        "winterthur",
    ],

    "st-gallen": [
        "st. gallen",
        "st.gallen",
        "saint-gall",
        "st gall",
        "sankt gallen",
    ],

    "lugano-ticino": [
        "lugano",
        "ticino",
        "tessin",
        "locarno",
        "bellinzona",
        "mendrisio",
        "chiasso",
    ],

    "zug": [
        "zug",
        "zoug",
    ],

    "biel-bienne": [
        "biel",
        "bienne",
        "biel/bienne",
    ],

    "fribourg": [
        "fribourg",
        "freiburg",
    ],

    "neuchatel": [
        "neuchâtel",
        "neuchatel",
        "neuenburg",
    ],

    "thun": [
        "thun",
        "thoune",
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
    ],

    "sion-valais": [
        "sion",
        "valais",
        "wallis",
        "martigny",
        "brig",
        "visp",
        "zermatt",
    ],

    "aarau-aargau": [
        "aarau",
        "aargau",
        "argovie",
        "baden",
        "wettingen",
    ],

    "schaffhausen": [
        "schaffhausen",
        "schaffhouse",
    ],

    "solothurn": [
        "solothurn",
        "soleure",
        "olten",
    ],

}


# =========================================================
# Other Swiss regions
# =========================================================

OTHER_SWISS_ALIASES = [

    # Central Switzerland

    "uri",
    "altdorf",

    "schwyz",
    "einsiedeln",
    "pfäffikon",
    "pfaeffikon",

    "obwalden",
    "sarnen",

    "nidwalden",
    "stans",

    # Eastern Switzerland

    "glarus",
    "glarner",

    "appenzell",
    "herisau",

    "thurgau",
    "thurgovie",
    "frauenfeld",
    "kreuzlingen",

    # Western Switzerland

    "jura",
    "delémont",
    "delemont",

]


# =========================================================
# National-level terms
# =========================================================

NATIONAL_ALIASES = [

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

    # French

    "suisse",
    "conseil fédéral",
    "conseil federal",
    "confédération",
    "confederation",
    "conseil national",

    # Italian

    "svizzera",
    "consiglio federale",
    "confederazione",

    # English

    "switzerland",
    "swiss federal",
    "federal council",

]


# =========================================================
# Helpers
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    text = text.lower()

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

    alias = normalize_text(
        alias
    )

    # Avoid partial matches for simple short names.
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


# =========================================================
# Main classifier
# =========================================================

def classify_region_slugs(article):

    """
    ArticleからRegion.slugの候補を返す。

    優先順位：

    1. 明示された主要地域
    2. その他のスイス地域
    3. 全国ニュース
    4. 不明
    """

    text = " ".join([
        article.title_original or "",
        article.title_ja or "",
        article.summary_original or "",
        article.summary_ja or "",
    ])

    text = normalize_text(
        text
    )

    matched_slugs = []

    # =====================================================
    # Major regions
    # =====================================================

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

    if matched_slugs:

        # Preserve order + remove duplicates
        return list(
            dict.fromkeys(
                matched_slugs
            )
        )

    # =====================================================
    # Other Swiss regions
    # =====================================================

    if any(
        contains_alias(
            text,
            alias,
        )
        for alias in OTHER_SWISS_ALIASES
    ):

        return [
            "other"
        ]

    # =====================================================
    # Switzerland-wide
    # =====================================================

    if any(
        contains_alias(
            text,
            alias,
        )
        for alias in NATIONAL_ALIASES
    ):

        return [
            "switzerland"
        ]

    # =====================================================
    # Unknown
    # =====================================================

    return [
        "unknown"
    ]