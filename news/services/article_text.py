import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; YahanNews/1.0)"
)

MAX_BODY_CHARS = 4000

MIN_PARAGRAPH_CHARS = 40

# RSSの紹介文がこれより長ければ本文を取りに行かない
ENOUGH_SUMMARY_CHARS = 1200


def fetch_article_body(url):
    """
    記事ページから本文の冒頭を取り出す。
    取得できない場合（有料記事・エラーなど）は空文字。
    """

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=(5, 15),
        )

        response.raise_for_status()

    except requests.RequestException:

        return ""

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
            "figure",
        ]
    ):
        tag.decompose()

    container = (
        soup.find("article")
        or soup.find("main")
        or soup.body
    )

    if container is None:
        return ""

    paragraphs = []
    total = 0

    for paragraph in container.find_all("p"):

        text = " ".join(
            paragraph.get_text(
                " ",
                strip=True,
            ).split()
        )

        if len(text) < MIN_PARAGRAPH_CHARS:
            continue

        paragraphs.append(
            text
        )

        total += len(text)

        if total >= MAX_BODY_CHARS:
            break

    return "\n".join(
        paragraphs
    )[:MAX_BODY_CHARS]


def article_input_text(article):
    """
    AIに渡す記事内容。
    紹介文が短い場合は本文の冒頭も加える。
    """

    summary = (
        article.summary_original
        or ""
    ).strip()

    if len(summary) >= ENOUGH_SUMMARY_CHARS:
        return summary

    # SBB の運行情報はリンク先が共通ページなので、本文を取りに行かない
    if "#sbb-" in article.source_url:
        return summary

    body = fetch_article_body(
        article.source_url
    )

    if not body:
        return summary

    # 本文に紹介文が含まれていれば重複させない
    if summary and summary[:80] in body:
        return body

    return (
        f"{summary}\n\n{body}"
        if summary
        else body
    )
