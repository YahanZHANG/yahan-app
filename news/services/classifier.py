from news.models import Topic


TOPIC_KEYWORDS = {
    "politics": [
        "bundesrat",
        "bundesversammlung",
        "parlament",
        "regierung",
        "nationalrat",
        "ständerat",
        "abstimmung",
        "wahl",
        "wahlen",
        "politik",
        "gesetz",
        "initiative",
        "referendum",
    ],

    "economy": [
        "wirtschaft",
        "unternehmen",
        "firma",
        "bank",
        "banken",
        "börse",
        "aktie",
        "aktien",
        "franken",
        "inflation",
        "konjunktur",
        "arbeitslosigkeit",
        "arbeitsmarkt",
    ],

    "society": [
        "polizei",
        "unfall",
        "brand",
        "feuerwehr",
        "gericht",
        "kriminalität",
        "festnahme",
        "verhaftet",
        "schule",
        "bildung",
    ],

    "life": [
        "miete",
        "mieten",
        "wohnung",
        "wohnungen",
        "krankenkasse",
        "prämien",
        "steuer",
        "steuern",
        "sbb",
        "bahn",
        "zug",
        "verkehr",
        "migration",
        "aufenthalt",
        "familie",
        "kinder",
    ],

    "technology": [
        "technologie",
        "digital",
        "digitalisierung",
        "internet",
        "cyber",
        "künstliche intelligenz",
        "ki",
        "forschung",
        "wissenschaft",
        "robotik",
    ],

    "health": [
        "gesundheit",
        "medizin",
        "spital",
        "spitäler",
        "arzt",
        "ärzte",
        "krankheit",
        "virus",
        "impfung",
        "medikament",
    ],

    "environment": [
        "klima",
        "umwelt",
        "energie",
        "gletscher",
        "wetter",
        "hochwasser",
        "dürre",
        "hitze",
        "schnee",
        "lawine",
    ],

    "culture": [
        "kultur",
        "musik",
        "film",
        "kino",
        "theater",
        "kunst",
        "festival",
        "museum",
    ],

    "sports": [
        "sport",
        "fussball",
        "fußball",
        "tennis",
        "ski",
        "skifahren",
        "hockey",
        "eishockey",
        "formel 1",
    ],
}


def classify_article(article):
    """
    タイトルとRSS要約から記事テーマを推定する。
    複数テーマの付与を許可する。
    """

    text = (
        f"{article.title_original} "
        f"{article.summary_original}"
    ).lower()

    matched_topics = []

    for slug, keywords in TOPIC_KEYWORDS.items():

        if any(
            keyword in text
            for keyword in keywords
        ):

            try:
                topic = Topic.objects.get(
                    slug=slug,
                    is_active=True,
                )

            except Topic.DoesNotExist:
                continue

            matched_topics.append(
                topic
            )

    if matched_topics:
        article.topics.set(
            matched_topics
        )

    return matched_topics