"""
同じ出来事を報じた記事を1つにまとめる。

1. 日本語タイトル・要約の「言葉の重なり」で候補を探す（無料・アプリ内）
   よくある言葉（スイス、した…）は重みを小さくする。
2. とても似ていればそのまままとめる。
   ある程度似ている候補だけ AI に同じ出来事か確認する（1回ごく少額）。
"""

import math
import re
import unicodedata
from collections import Counter
from datetime import timedelta

from django.db.models import Count, F, Q

from config.services.ai_client import (
    generate_json,
)

from news.models import Article


# この似ている度以上なら AI に聞かずに同じニュースとみなす
SAME_THRESHOLD = 0.6

# この範囲は AI に同じ出来事か確認する
CANDIDATE_THRESHOLD = 0.2

# 1記事あたり AI に確認する候補の数
MAX_AI_CHECKS = 3

# 前後この時間内に公開された記事だけ比較する
WINDOW = timedelta(hours=48)

SUMMARY_CHARS = 300

CJK_RUN = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]+"
)

LATIN_WORD = re.compile(
    r"[a-z0-9\u00c0-\u024f]{2,}"
)


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


def _article_text(article):

    title = (
        article.title_ja
        or article.title_original
    )

    summary = (
        article.summary_ja
        or article.summary_original
        or ""
    )

    return title, summary[:SUMMARY_CHARS]


def shingles(text):
    """
    文章を比べやすい単位に分ける。
    日本語は2文字ずつ、英数字は単語ごと。
    """

    text = unicodedata.normalize(
        "NFKC",
        text or "",
    ).lower()

    result = set()

    for run in CJK_RUN.findall(text):

        if len(run) == 1:
            result.add(run)
            continue

        for index in range(len(run) - 1):
            result.add(
                run[index:index + 2]
            )

    for word in LATIN_WORD.findall(text):
        result.add(
            "w:" + word
        )

    return result


def article_shingles(article):

    title, summary = _article_text(
        article
    )

    # タイトルの言葉は要約の言葉より重く見る
    return (
        {("t", item) for item in shingles(title)}
        | {("s", item) for item in shingles(summary)}
    )


class Similarity:
    """
    比べる記事の集まりから、言葉ごとの重み（珍しいほど重い）を作る。
    """

    def __init__(self, articles):

        self.shingles = {
            article.pk: article_shingles(article)
            for article in articles
        }

        frequency = Counter()

        for items in self.shingles.values():
            frequency.update(
                {item[1] for item in items}
            )

        total = max(
            len(self.shingles),
            1,
        )

        self.weights = {
            word: math.log(
                (total + 1) / (count + 0.5)
            )
            for word, count in frequency.items()
        }

    def add(self, article):

        if article.pk not in self.shingles:
            self.shingles[article.pk] = article_shingles(
                article
            )

    def _weight(self, item):

        kind, word = item

        weight = self.weights.get(
            word,
            math.log(2),
        )

        return weight * (2 if kind == "t" else 1)

    def score(self, article, other):

        a = self.shingles[article.pk]
        b = self.shingles[other.pk]

        if not a or not b:
            return 0.0

        # タイトル同士・要約同士を同じ言葉として扱う
        words_a = {item[1]: item for item in a}
        words_b = {item[1]: item for item in b}

        shared = sum(
            max(
                self._weight(words_a[word]),
                self._weight(words_b[word]),
            )
            for word in words_a.keys() & words_b.keys()
        )

        total_a = sum(
            self._weight(item)
            for item in words_a.values()
        )

        total_b = sum(
            self._weight(item)
            for item in words_b.values()
        )

        if not total_a or not total_b:
            return 0.0

        return shared / math.sqrt(
            total_a * total_b
        )


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


def confirm_same_event(article, other):

    def block(item):

        return (
            f"媒体: {item.source.name}\n"
            f"タイトル: {item.title_ja or item.title_original}\n"
            f"内容: {(item.summary_ja or item.summary_original)[:1500]}"
        )

    result = generate_json(
        instructions=CONFIRM_INSTRUCTIONS,
        input_text=(
            "記事A\n"
            f"{block(article)}\n\n"
            "記事B\n"
            f"{block(other)}"
        ),
        schema=CONFIRM_SCHEMA,
        name="same_event",
        max_tokens=100,
    )

    return bool(
        result.data["same_event"]
    )


def find_duplicate_root(
    article,
    candidates,
    similarity,
    use_ai=True,
):
    """
    article と同じ出来事を扱う代表記事を返す。
    見つからなければ (None, None)。

    戻り値: (代表記事, 似ている度)
    """

    scored = []

    for other in candidates:

        if other.pk == article.pk:
            continue

        if abs(
            other.published_at
            - article.published_at
        ) > WINDOW:
            continue

        score = similarity.score(
            article,
            other,
        )

        if score >= CANDIDATE_THRESHOLD:

            scored.append(
                (score, other)
            )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    for score, other in scored[:MAX_AI_CHECKS]:

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


def with_source_count(queryset):
    """
    代表記事ごとに、報じた媒体数を source_count として付ける。
    """

    return queryset.annotate(
        source_count=(
            Count(
                "duplicates__source",
                filter=~Q(
                    duplicates__source=F("source")
                ),
                distinct=True,
            )
            + 1
        )
    )
