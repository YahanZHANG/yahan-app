"""Keyword matching and ranking for the search page.

Every word of the query must match somewhere (title, place, genre, text). Each
word also matches its spelling variants (Zuerich -> Zürich, チューリッヒ ->
Zürich), hiragana/katakana and a few synonyms people type in Japanese, German
or English. Results are ranked by where the words matched: a title hit counts
more than a hit in the description.
"""

import unicodedata

from outings.regions import CITY_ALIASES, REGION_NAMES, REGION_NAMES_JA, search_variants


FOLDS = (
    ("ä", "a"), ("ö", "o"), ("ü", "u"), ("ae", "a"), ("oe", "o"), ("ue", "u"),
    ("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("ß", "ss"),
)

SYNONYMS = [
    ["子ども", "子供", "こども", "キッズ", "kinder", "kids", "family", "ファミリー", "親子", "家族"],
    ["無料", "free", "gratis", "kostenlos"],
    ["コンサート", "konzert", "concert", "ライブ", "音楽", "musik", "music"],
    ["マーケット", "markt", "market", "マルシェ"],
    ["クリスマス", "weihnacht", "christmas", "xmas", "advent"],
    ["美術館", "博物館", "museum", "ミュージアム", "展示", "ausstellung", "exhibition"],
    ["ハイキング", "wandern", "wanderung", "hike", "hiking", "トレッキング"],
    ["お祭り", "祭り", "フェス", "festival"],
    ["ワークショップ", "workshop", "体験", "kurs"],
    ["映画", "kino", "film", "cinema"],
    ["演劇", "theater", "theatre", "舞台"],
    ["ジャズ", "jazz"],
    ["英語", "english", "englisch"],
    ["日本", "japan", "japanese", "japanisch"],
]

# Field weights: where a word matched says how relevant the result is.
TITLE, PLACE, GENRE, TEXT, ORIGINAL = 6, 4, 3, 2, 1

FAMILY_TAGS = {"family", "children", "baby"}


def normalize(text):
    text = unicodedata.normalize("NFKC", text or "").casefold()
    # Hiragana -> katakana, so こども finds コドモ and the other way round.
    text = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in text)
    for before, after in FOLDS:
        text = text.replace(before, after)
    return text


_SYNONYM_GROUPS = [{normalize(word) for word in group} for group in SYNONYMS]

# Every spelling of a city, so "Basel" also finds titles written as バーゼル.
_CITY_SPELLINGS = {}
for _alias, _city in CITY_ALIASES.items():
    _CITY_SPELLINGS.setdefault(normalize(_city), {normalize(_city)}).add(normalize(_alias))
for _spellings in list(_CITY_SPELLINGS.values()):
    for _spelling in _spellings:
        _CITY_SPELLINGS[_spelling] = _spellings


def tokens(query):
    """The query split into words, each with its normalized variants."""
    result = []
    for word in normalize(query).split():
        if len(word) == 1 and word.isascii():
            continue
        variants = {normalize(v) for v in search_variants(word)} | {word}
        for variant in list(variants):
            variants |= _CITY_SPELLINGS.get(variant, set())
        for group in _SYNONYM_GROUPS:
            if word in group:
                variants |= group
        result.append(variants)
    return result


def event_document(event):
    tags = [tag for tag in event.tags.all()]
    tag_slugs = {tag.slug for tag in tags}
    location = event.location
    flags = []
    if event.is_free:
        flags.append("無料 free")
    if tag_slugs & FAMILY_TAGS:
        flags.append("家族 子ども family")
    if event.language_barrier == "english":
        flags.append("英語 english")
    genre = [event.category.name if event.category_id and event.category else ""]
    genre += [tag.name for tag in tags] + flags
    place = []
    if location:
        place = [location.city, location.name, REGION_NAMES.get(location.canton, ""), REGION_NAMES_JA.get(location.canton, "")]
    return [
        (TITLE, normalize(f"{event.title} {event.title_original}")),
        (PLACE, normalize(" ".join(place))),
        (GENRE, normalize(" ".join(genre))),
        (TEXT, normalize(f"{event.highlight_ja} {event.summary_ja}")),
        (ORIGINAL, normalize(event.description_original)),
    ]


def trip_document(spot):
    return [
        (TITLE, normalize(f"{spot.title_ja} {spot.title_original}")),
        (GENRE, normalize(spot.get_spot_type_display())),
        (TEXT, normalize(spot.summary_ja)),
        (ORIGINAL, normalize(f"{spot.summary_original} {spot.description_original}")),
    ]


def score(document, words):
    """(matched word count, relevance) of a document for the query words."""
    matched, total = 0, 0
    for variants in words:
        best = max((weight for weight, text in document if any(v in text for v in variants)), default=0)
        if best:
            matched += 1
            total += best
    return matched, total
