import json
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from config.services.openai_client import (
    get_openai_client,
)

from news.models import (
    Article,
    NewsDigest,
)


MODEL = "gpt-5.6-luna"

MAX_ARTICLES = 100


OUTPUT_SCHEMA = {
    "type": "object",

    "properties": {

        "summary_ja": {
            "type": "string",
        },

        "highlights": {
            "type": "array",

            "items": {
                "type": "object",

                "properties": {

                    "tag": {
                        "type": "string",
                        "enum": [
                            "重要",
                            "複数媒体",
                            "暮らし",
                            "注目",
                        ],
                    },

                    "title": {
                        "type": "string",
                    },

                    "summary": {
                        "type": "string",
                    },

                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                },

                "required": [
                    "tag",
                    "title",
                    "summary",
                    "sources",
                ],

                "additionalProperties": False,
            },
        },
    },

    "required": [
        "summary_ja",
        "highlights",
    ],

    "additionalProperties": False,
}


INSTRUCTIONS = """
あなたはスイス在住の日本人向けニュースアプリ
「Yahan News」の編集者です。

今回新たに取得した複数のニュース記事を読み、
全体を俯瞰する「ニュースまとめ」を作成してください。

【最重要ルール】

・入力された記事だけを根拠にする
・入力にない事実を追加しない
・政治的な意見や評価を加えない
・煽情的な文章にしない
・同じ出来事を扱う記事は1つのニュースとしてまとめる
・同じ出来事が複数の異なる媒体で報じられている場合は
  重要度を高く評価する
・単なる媒体数だけで重要と決めず、
  スイス社会への影響も考慮する
・「だ」「である」調で書く

【優先するニュース】

以下を優先してください。

1. 複数の異なるニュース媒体が報じている出来事
2. スイス在住者の生活に直接影響するニュース
3. 政府、法律、国民投票、移民、税、健康保険、
   公共交通、安全、災害など重要性の高いニュース
4. スイス経済や雇用への影響が大きいニュース
5. その他、全国的に重要なニュース

広告、宣伝、ニュースレター、娯楽的な販促情報を
重要ニュースとして扱わないでください。

【ニュースまとめ本文】

その時間帯のスイスで何が起きているのか、
日本人が短時間で把握できる自然な日本語でまとめてください。

目安は4～8文程度です。

ニュースが少ない場合は無理に長くしないでください。

【Highlights】

重要な話題を最大4件選択してください。

同じ出来事が複数媒体で報道されている場合は、
sources にその媒体名を入れてください。

tag は以下から選択してください。

重要
複数媒体
暮らし
注目
"""


def generate_news_digest(
    period=None,
):

    now = timezone.now()

    local_now = timezone.localtime(
        now
    )


    if period is None:

        if local_now.hour < 12:
            period = "morning"

        else:
            period = "afternoon"


    digest_date = timezone.localdate()


    # 同じ時間帯ですでに作成済みなら、
    # 最初に使った開始時間を維持する
    existing_digest = (
        NewsDigest.objects
        .filter(
            digest_date=digest_date,
            period=period,
        )
        .first()
    )


    if existing_digest:

        source_from = (
            existing_digest.source_from
        )

    else:

        previous_digest = (
            NewsDigest.objects
            .exclude(
                digest_date=digest_date,
                period=period,
            )
            .order_by(
                "-generated_at"
            )
            .first()
        )


        if previous_digest:

            source_from = (
                previous_digest.generated_at
            )

        else:

            source_from = (
                now
                - timedelta(hours=12)
            )


    articles = list(
        Article.objects
        .filter(
            fetched_at__gt=source_from,
            fetched_at__lte=now,
        )
        .filter(
            Q(
                original_language="ja"
            )
            |
            Q(
                ai_processed_at__isnull=False
            )
        )
        .select_related(
            "source"
        )
        .order_by(
            "-published_at"
        )[:MAX_ARTICLES]
    )


    if not articles:
        return None


    article_blocks = []


    for index, article in enumerate(
        articles,
        start=1,
    ):

        title = (
            article.title_ja
            or article.title_original
        )

        summary = (
            article.summary_ja
            or article.summary_original
        )


        article_blocks.append(
            f"""
ARTICLE {index}

SOURCE:
{article.source.name}

TITLE:
{title}

SUMMARY:
{summary}
"""
        )


    input_text = "\n".join(
        article_blocks
    )


    client = get_openai_client()


    response = client.responses.create(

        model=MODEL,

        reasoning={
            "effort": "none",
        },

        instructions=INSTRUCTIONS,

        input=input_text,

        text={
            "format": {
                "type": "json_schema",
                "name": "news_digest",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            }
        },

        max_output_tokens=1200,

        store=False,
    )


    result = json.loads(
        response.output_text
    )


    digest, _ = (
        NewsDigest.objects
        .update_or_create(

            digest_date=digest_date,

            period=period,

            defaults={

                "summary_ja":
                    result["summary_ja"],

                "highlights":
                    result["highlights"],

                "article_count":
                    len(articles),

                "source_from":
                    source_from,

                "source_to":
                    now,

                "ai_model":
                    MODEL,

                "input_tokens":
                    response.usage.input_tokens,

                "output_tokens":
                    response.usage.output_tokens,
            },
        )
    )


    return digest