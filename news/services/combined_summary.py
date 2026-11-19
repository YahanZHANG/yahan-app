"""
複数の媒体が同じ出来事を報じたときの「まとめ要約」。

代表記事（duplicate_of が空の記事）と、その重複記事を
媒体ごとに1件ずつ AI に渡し、各社の報道を均等に反映した
要約を作る。結果は代表記事の combined_summary_ja に入れる。
"""

from config.services.ai_client import (
    generate_json,
)

from news.services.ai_enricher import (
    BASE_INSTRUCTIONS,
)

from news.services.article_text import (
    article_input_text,
)


# 1社あたり AI に渡す本文（冒頭だけ）
PER_SOURCE_CHARS = 1500

# まとめに使う媒体の上限（多すぎると入力が長くなる）
MAX_SOURCES = 6

MAX_OUTPUT_TOKENS = 1200


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary_ja": {
            "type": "string",
        },
    },
    "required": [
        "summary_ja",
    ],
    "additionalProperties": False,
}


COMBINED_RULES = """
【今回の作業：複数社の報道のまとめ】

同じ出来事について、複数の媒体の記事が与えられます。
summary_ja に、それらをまとめた日本語の要約を書いてください。

・全体で最大6文（5～6文が目安。情報が少なければ短くてよい）
・どれか1社の記事に偏らず、各社の報道を均等に反映する
・各社から少なくとも1つは、その記事ならではの情報や視点を入れる
・各社で数字や見方が違うときは
  「〇〇によると…、一方△△は…」のように媒体名を添えて書き分ける
・同じ内容は1回だけ書く
・引用（発言のかぎかっこ）はできるだけ避け、自分の言葉で書く
・「…」で文を途中で切らない
・タイトル、テーマ、暮らしのお知らせの判定は今回は不要
"""


COMBINED_INSTRUCTIONS = (
    BASE_INSTRUCTIONS
    + COMBINED_RULES
)


def group_key(articles):
    """
    まとめに使った記事の組み合わせ（変わったら作り直す）。
    """

    return ",".join(
        str(article.id)
        for article in sorted(
            articles,
            key=lambda item: item.id,
        )
    )[:200]


def group_articles(root):
    """
    まとめに使う記事（媒体ごとに1件、最大 MAX_SOURCES 件）。
    """

    return root.source_articles[:MAX_SOURCES]


def summarize_group(root):
    """
    代表記事の combined_summary_ja を作り直す。
    1社だけになった場合は消す。保存したら True。
    """

    articles = group_articles(
        root
    )

    key = group_key(
        articles
    )

    if len(articles) < 2:

        if not root.combined_summary_ja and not root.combined_from:
            return False

        root.combined_summary_ja = ""
        root.combined_from = ""

        root.save(
            update_fields=[
                "combined_summary_ja",
                "combined_from",
            ]
        )

        return True

    if key == root.combined_from and root.combined_summary_ja:
        return False

    blocks = []

    for number, article in enumerate(
        articles,
        start=1,
    ):

        text = (
            article_input_text(article)
            or article.summary_ja
            or ""
        )[:PER_SOURCE_CHARS]

        blocks.append(
            f"記事{number}\n"
            f"媒体: {article.source.name}\n"
            f"元の言語: {article.original_language}\n"
            f"タイトル: {article.title_original}\n"
            f"内容:\n{text}"
        )

    result = generate_json(
        instructions=COMBINED_INSTRUCTIONS,
        input_text=(
            "\n\n".join(blocks)
            + "\n\n上記の情報だけを使って処理してください。"
        ),
        schema=OUTPUT_SCHEMA,
        name="news_combined_summary",
        max_tokens=MAX_OUTPUT_TOKENS,
    )

    root.combined_summary_ja = (
        result.data["summary_ja"].strip()
    )

    root.combined_from = key

    root.save(
        update_fields=[
            "combined_summary_ja",
            "combined_from",
        ]
    )

    return True
