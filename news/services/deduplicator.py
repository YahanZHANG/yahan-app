import json
import math
from datetime import timedelta

from django.db.models import Q

from config.services.openai_client import (
    get_openai_client,
)

from news.models import Article


EMBEDDING_MODEL = "text-embedding-3-small"

EMBEDDING_DIMENSIONS = 512

CONFIRM_MODEL = "gpt-5.6-luna"

# この類似度以上なら同じニュースとみなす
SAME_THRESHOLD = 0.88

# この範囲はAIに同じ出来事か確認する
CANDIDATE_THRESHOLD = 0.75

# 前後この時間内に公開された記事だけ比較する
WINDOW = timedelta(hours=48)

EMBED_BATCH_SIZE = 100


CONFIRM_SCHEMA = {
    "type": "object",
    "properties": {
        "same_event": {
            "type": "boolean",
        },
    },
    "required": [
        "same_event",
    ],
    "additionalProperties": False,
}


CONFIRM_INSTRUCTIONS = """
2つのニュース記事が、同じ出来事・同じ発表を
報じているかを判定してください。

・同じ出来事の続報や、別の媒体による同じ内容の報道は true
・同じテーマでも別の出来事（別の事故、別の投票、別の企業）は false
・判断に迷う場合は false
"""


def _embedding_text(article):

    title = (
        article.title_ja
        or article.title_original
    )

    summary = (
        article.summary_ja
        or article.summary_original
    )

    return f"{title}\n{summary}"[:4000]


def _cosine(a, b):

    dot = sum(
        x * y
        for x, y in zip(a, b)
    )

    norm_a = math.sqrt(
        sum(x * x for x in a)
    )

    norm_b = math.sqrt(
        sum(y * y for y in b)
    )

    if not norm_a or not norm_b:
        return 0.0

    return dot / (norm_a * norm_b)


def ready_articles():
    """
    日本語タイトル・要約がそろった記事。
    """

    return Article.objects.filter(
        Q(
            original_language="ja"
        )
        |
        Q(
            ai_processed_at__isnull=False
        )
    )


def embed_articles(
    articles,
    save=True,
):
    """
    埋め込みがない記事にまとめて埋め込みを付ける。
    """

    articles = [
        article
        for article in articles
        if article.embedding is None
    ]

    if not articles:
        return 0

    client = get_openai_client()

    for start in range(
        0,
        len(articles),
        EMBED_BATCH_SIZE,
    ):

        batch = articles[
            start:start + EMBED_BATCH_SIZE
        ]

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input=[
                _embedding_text(article)
                for article in batch
            ],
        )

        for article, item in zip(
            batch,
            response.data,
        ):

            article.embedding = [
                round(value, 6)
                for value in item.embedding
            ]

            if save:

                article.save(
                    update_fields=[
                        "embedding",
                    ]
                )

    return len(articles)


def confirm_same_event(article, other):

    client = get_openai_client()

    def block(item):

        return (
            f"媒体: {item.source.name}\n"
            f"タイトル: {item.title_ja or item.title_original}\n"
            f"内容: {(item.summary_ja or item.summary_original)[:1500]}"
        )

    response = client.responses.create(
        model=CONFIRM_MODEL,

        reasoning={
            "effort": "none",
        },

        instructions=CONFIRM_INSTRUCTIONS,

        input=(
            "記事A\n"
            f"{block(article)}\n\n"
            "記事B\n"
            f"{block(other)}"
        ),

        text={
            "format": {
                "type": "json_schema",
                "name": "same_event",
                "strict": True,
                "schema": CONFIRM_SCHEMA,
            }
        },

        max_output_tokens=50,

        store=False,
    )

    result = json.loads(
        response.output_text
    )

    return bool(
        result["same_event"]
    )


def find_duplicate_root(
    article,
    candidates,
    use_ai=True,
):
    """
    article と同じ出来事を扱う代表記事を返す。
    見つからなければ None。

    戻り値: (代表記事, 類似度)
    """

    scored = []

    for other in candidates:

        if other.pk == article.pk:
            continue

        if other.embedding is None:
            continue

        if abs(
            other.published_at
            - article.published_at
        ) > WINDOW:
            continue

        score = _cosine(
            article.embedding,
            other.embedding,
        )

        if score >= CANDIDATE_THRESHOLD:

            scored.append(
                (score, other)
            )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    for score, other in scored[:3]:

        if score >= SAME_THRESHOLD:
            same = True

        elif use_ai:
            same = confirm_same_event(
                article,
                other,
            )

        else:
            same = False

        if same:

            root = other

            if other.duplicate_of_id:
                root = other.duplicate_of

            return root, score

    return None, None
