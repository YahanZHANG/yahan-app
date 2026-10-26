from django.utils import timezone

from config.services.ai_client import (
    generate_json,
)

from news.models import Topic

from news.services.article_text import (
    article_input_text,
)

from news.management.commands.fetch_sbb_info import (
    SOURCE_NAME as SBB_SOURCE_NAME,
)

from news.services.japanese_classifier import (
    get_other_topic,
)


MAX_INPUT_CHARS = 10000

MAX_OUTPUT_TOKENS = 2000

# 失敗が続く記事を毎回再送しないための上限
MAX_AI_ATTEMPTS = 3

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

        "life_alert": {
            "type": "boolean",
        },
    },

    "required": [
        "title_ja",
        "summary_ja",
        "topics",
        "life_alert",
    ],

    "additionalProperties": False,
}


# 「暮らしのお知らせ」の判定基準（後から付け直すコマンドでも使う）
LIFE_ALERT_RULES = """
【life_alert（暮らしのお知らせ）】

スイスに住む人が「知らないと困る・予定を変える」
具体的な生活情報なら true にする。例:

・ストライキ、デモによる交通規制
・電車、バス、道路、空港の運休・遅延・通行止め・工事
・税金、保険、手続きなどの期限や制度の変更日
・祝日や行事の日の店・役所の営業時間
・停電、断水、悪天候や自然災害の警報、避難
・料金や運賃の変更（いつから・いくら）

一般的な政治・経済の話題、事件、事故の報道、
スポーツ、文化、意見記事は false にする。
迷う場合は false にする。
"""


INSTRUCTIONS = """
あなたはスイス在住の日本人向けニュースアプリ
「Swiss News」の編集者です。

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

【地名表記】

・Zürich を日本語表記する場合は、必ず
  「チューリッヒ」とする
・「チューリヒ」は使用しない
・スイスの地名は、一般的な日本語表記が
  十分に定着していない場合、
  無理にカタカナ表記にしない
・小さな都市、自治体、地区、村、山、谷、
  駅名などは、原文表記を優先する
・必要に応じて初出のみ
  「Zürich（チューリッヒ）」
  のように原文表記と日本語表記を併記してよい
・同じ記事内で、同じ地名について
  原文表記と日本語表記を何度も併記しない
・不明な地名の日本語表記を推測して作らない
・原文の正式な綴りやアクセント記号を
  可能な限り保持する

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
""" + LIFE_ALERT_RULES


def enrich_article(article):

    article_text = article_input_text(
        article
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

    result = generate_json(
        instructions=INSTRUCTIONS,
        input_text=input_text,
        schema=OUTPUT_SCHEMA,
        name="news_enrichment",
        # 日本語の長い要約（最大10文）でも
        # 途中で切れないよう余裕を持たせる。
        max_tokens=MAX_OUTPUT_TOKENS,
    )

    data = result.data

    article.title_ja = (
        data["title_ja"].strip()
    )

    article.summary_ja = (
        data["summary_ja"].strip()
    )

    article.ai_processed_at = (
        timezone.now()
    )

    article.ai_model = result.model

    article.ai_error = ""

    # SBB の運行情報はいつも暮らしのお知らせ
    article.life_alert = bool(
        data.get("life_alert")
        or article.source.name == SBB_SOURCE_NAME
    )

    article.save(
        update_fields=[
            "title_ja",
            "summary_ja",
            "ai_processed_at",
            "ai_model",
            "ai_error",
            "life_alert",
        ]
    )

    # ========================================
    # Topic classification
    # ========================================

    topics = list(
        Topic.objects.filter(
            slug__in=data["topics"],
            is_active=True,
        )
    )

    # AIがテーマを返さなかった場合、
    # または有効なTopicが見つからない場合。

    if not topics:

        topics = [
            get_other_topic()
        ]

    article.topics.set(
        topics
    )

    return {
        "title_ja": article.title_ja,
        "summary_ja": article.summary_ja,
        "topics": [
            topic.name
            for topic in topics
        ],
        "life_alert": article.life_alert,
        "usage": result,
    }