"""Canton definitions shared by every Outings screen and the Eventfrog import.

Keep this the only list of cantons: filters, preferences, member posts and the
importer previously had five different copies that disagreed (Bern was missing
from preferences, Schwyz could be posted but never filtered).
"""

# Cantons covered by the daily Eventfrog import.
EVENTFROG_REGIONS = ("ZH", "BS", "BL", "AG", "ZG", "LU", "BE")

# Every canton a member can post to or choose as a favourite.
REGIONS = (
    ("ZH", "チューリッヒ", "Zürich"),
    ("BS", "バーゼル・シュタット", "Basel-Stadt"),
    ("BL", "バーゼル・ラント", "Basel-Landschaft"),
    ("AG", "アールガウ", "Aargau"),
    ("ZG", "ツーク", "Zug"),
    ("LU", "ルツェルン", "Luzern"),
    ("BE", "ベルン", "Bern"),
    ("SZ", "シュヴィーツ", "Schwyz"),
    ("SO", "ゾロトゥルン", "Solothurn"),
    ("NW", "ニトヴァルデン", "Nidwalden"),
    ("OW", "オプヴァルデン", "Obwalden"),
)

REGION_CODES = frozenset(code for code, _, _ in REGIONS)

REGION_NAMES = {code: name for code, _, name in REGIONS}

REGION_NAMES_JA = {code: name_ja for code, name_ja, _ in REGIONS}

# (code, label) pairs for templates and form choices.
REGION_CHOICES = [(code, name) for code, _, name in REGIONS]


def clean_region(value):
    value = str(value or "").strip().upper()
    return value if value in REGION_CODES else ""


def clean_regions(values):
    return [code for code in dict.fromkeys(clean_region(v) for v in values) if code]


# Japanese and English spellings people type into the search box, mapped to the
# spelling stored on EventLocation.city.
CITY_ALIASES = {
    "チューリッヒ": "Zürich",
    "チューリヒ": "Zürich",
    "zurich": "Zürich",
    "zuerich": "Zürich",
    "バーゼル": "Basel",
    "basle": "Basel",
    "ベルン": "Bern",
    "berne": "Bern",
    "ルツェルン": "Luzern",
    "ルッツェルン": "Luzern",
    "lucerne": "Luzern",
    "ツーク": "Zug",
    "ヴィンタートゥール": "Winterthur",
    "ヴィンタートゥーア": "Winterthur",
    "winterthur": "Winterthur",
    "アーラウ": "Aarau",
    "バーデン": "Baden",
    "トゥーン": "Thun",
    "ビール": "Biel/Bienne",
    "biel": "Biel/Bienne",
    "bienne": "Biel/Bienne",
    "リースタル": "Liestal",
    "インターラーケン": "Interlaken",
}


def search_variants(query):
    """Return the query plus the stored spellings it may stand for."""
    query = (query or "").strip()
    if not query:
        return []
    variants = [query]
    alias = CITY_ALIASES.get(query.casefold())
    if alias:
        variants.append(alias)
    # Swiss German transliteration: "Zuerich" -> "Zürich".
    folded = (
        query.replace("ue", "ü").replace("oe", "ö").replace("ae", "ä")
        .replace("Ue", "Ü").replace("Oe", "Ö").replace("Ae", "Ä")
    )
    if folded != query:
        variants.append(folded)
    return list(dict.fromkeys(variants))
