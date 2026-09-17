import re


SKIP_PATTERNS = [
    # English
    r"\bnewsletter\b",
    r"\bsponsored\b",
    r"\badvertorial\b",
    r"\bpromotion\b",

    # German
    r"\bgewinnspiel\b",
    r"\bquiz\b",
    r"\bcomics?\b",
    r"\bwerbung\b",
    r"\bpublireportage\b",

    # French
    r"\bconcours\b",
    r"\bpublicité\b",
    r"\bsponsorisé\b",

    # Italian
    r"\bpubblicità\b",
    r"\bpromozione\b",

    # Japanese
    r"ニュースレター",
    r"広告",
    r"プレゼント企画",
]


SKIP_URL_PARTS = [
    "/newsletter",
    "/newsletter/",
    "/gewinnspiel",
    "/quiz/",
    "/comics/",
    "/sponsored/",
    "/advertorial/",
]


def should_skip_article(
    source_name,
    title,
    summary="",
    url="",
):
    """
    広告・ニュースレター・漫画・懸賞など、
    Yahan Newsに不要なコンテンツを除外する。

    AI APIを呼ぶ前に実行する。
    """

    title = title or ""
    summary = summary or ""
    url = url or ""

    text = (
        f"{title} {summary}"
    ).lower()

    url_lower = url.lower()


    # URLで除外
    if any(
        part in url_lower
        for part in SKIP_URL_PARTS
    ):
        return True


    # タイトル・概要で除外
    for pattern in SKIP_PATTERNS:

        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return True


    # -------------------------
    # Source-specific rules
    # -------------------------

    if source_name == "SWI swissinfo.ch":

        # SWIのニュースレター勧誘など
        if "無料ニュースレター" in title:
            return True


    return False