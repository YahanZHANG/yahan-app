import json

from django.utils import timezone

from config.services.openai_client import (
    get_openai_client,
)

from news.models import Topic


MODEL = "gpt-5.6-luna"

MAX_INPUT_CHARS = 10000

TOPIC_SLUGS = [
    "politics",
    "economy",
    "society",
    "life",
    "technology",
    "health",
    "environment",
    "culture",
    "sports",
]


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title_ja": {
            "type": "string",
        },

        "summary_ja": {
            "type": "string",
        },

        "topics": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": TOPIC_SLUGS,
            },
        },
    },

    "required": [
        "title_ja",
        "summary_ja",
        "topics",
    ],

    "additionalProperties": False,
}


INSTRUCTIONS = """
あなたはスイス在住の日本人向けニュースアプリ
「Yahan News」の編集者です。

与えられたニュース情報だけを使って、
自然で正確な日本語ニュースを作成してください。

【重要】
・入力にない事実を追加しない
・推測しない
・意見や政治的評価を加えない
・原文の意味を変えない
・煽情的な表現を避ける
・日本の読者に読みやすい自然な日本語にする
・記事タイトルは簡潔にする
・文章数を満たすために情報を水増ししない
・重要な情報を落とさないことを文章数より優先する
・「だ」「である」調で書く

【要約の長さ】

・短いニュースや情報量の少ない記事：
  2～4文程度

・通常の記事：
  2～5文程度

・情報量が多く、日本人読者に重要な記事：
  5～10文程度

・原文の情報量に応じて長さを調整する
・情報が少ない記事を無理に長くしない

【スイス固有名詞】

Bundesrat
→ 連邦参事会

Bundesversammlung
→ 連邦議会

Nationalrat
→ 国民議会

Ständerat
→ 全州議会

Kanton
→ 州

Gemeinde
→ 自治体

Schweizerische Nationalbank / SNB
→ スイス国立銀行（SNB）

SBB
→ スイス連邦鉄道（SBB）

SECO
→ スイス連邦経済省経済事務局（SECO）

【テーマ】

politics
政治、政府、議会、国民投票、法律、外交

economy
経済、企業、金融、雇用、物価

society
社会、事件、事故、犯罪、教育

life
住宅、税金、保険、公共交通、移民、
家族、生活制度、消費者情報

technology
科学、研究、AI、IT、デジタル、技術

health
医療、健康、病院、感染症、医薬品

environment
環境、気候、エネルギー、自然災害

culture
文化、芸術、映画、音楽、エンタメ

sports
スポーツ

記事に明確に関連するテーマだけを選択してください。
複数選択可能です。
"""

def enrich_article(article):

    client = get_openai_client()

    article_text = (
        article.summary_original
        or ""
    )[:MAX_INPUT_CHARS]


    input_text = f"""
    ニュース提供元:
    {article.source.name}

    元の言語:
    {article.original_language}

    タイトル:
    {article.title_original}

    記事内容:
    {article_text}

    上記の情報だけを使って処理してください。
    """


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
                "name": "news_enrichment",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            }
        },

        max_output_tokens=500,

        store=False,
    )


    result = json.loads(
        response.output_text
    )


    article.title_ja = (
        result["title_ja"].strip()
    )

    article.summary_ja = (
        result["summary_ja"].strip()
    )

    article.ai_processed_at = (
        timezone.now()
    )

    article.ai_model = MODEL

    article.ai_error = ""

    article.save(
        update_fields=[
            "title_ja",
            "summary_ja",
            "ai_processed_at",
            "ai_model",
            "ai_error",
        ]
    )


    topics = Topic.objects.filter(
        slug__in=result["topics"],
        is_active=True,
    )

    article.topics.set(
        topics
    )


    return {
        "title_ja": article.title_ja,
        "summary_ja": article.summary_ja,
        "topics": list(
            topics.values_list(
                "name",
                flat=True,
            )
        ),
        "usage": response.usage,
    }