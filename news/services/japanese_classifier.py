from news.models import Topic


TOPIC_KEYWORDS = {
    "politics": [
        "連邦参事会",
        "連邦議会",
        "国民議会",
        "全州議会",
        "国民投票",
        "住民投票",
        "選挙",
        "政府",
        "閣僚",
        "大統領",
        "首相",
        "政党",
        "議会",
        "法案",
        "法律",
        "外交",
        "制裁",
        "民主主義",
        "移民政策",
        "難民",
        "亡命",
    ],

    "economy": [
        "経済",
        "景気",
        "企業",
        "輸出",
        "輸入",
        "貿易",
        "FTA",
        "自由貿易",
        "銀行",
        "金融",
        "金利",
        "物価",
        "インフレ",
        "雇用",
        "失業",
        "賃金",
        "フラン",
        "スイス国立銀行",
        "SNB",
        "UBS",
    ],

    "society": [
        "事件",
        "事故",
        "警察",
        "裁判",
        "逮捕",
        "犯罪",
        "死亡",
        "死者",
        "負傷",
        "火災",
        "教育",
        "学校",
        "大学",
        "社会",
        "ジェンダー",
        "男女平等",
    ],

    "life": [
        "暮らし",
        "住宅",
        "家賃",
        "健康保険",
        "保険料",
        "年金",
        "税金",
        "税制",
        "交通",
        "鉄道",
        "SBB",
        "スイス連邦鉄道",
        "郵便",
        "ビザ",
        "滞在許可",
        "自治体",
    ],

    "technology": [
        "科学",
        "技術",
        "テクノロジー",
        "AI",
        "人工知能",
        "研究",
        "ETH",
        "EPFL",
        "宇宙",
        "デジタル",
        "サイバー",
    ],

    "health": [
        "医療",
        "健康",
        "病院",
        "感染",
        "感染症",
        "ワクチン",
        "結核",
        "医薬品",
        "患者",
        "疾病",
    ],

    "environment": [
        "環境",
        "気候",
        "気候変動",
        "温暖化",
        "洪水",
        "干ばつ",
        "ひょう",
        "暴風雨",
        "災害",
        "地下水",
        "自然",
        "エネルギー",
    ],

    "culture": [
        "文化",
        "映画",
        "音楽",
        "芸術",
        "演劇",
        "文学",
        "美術",
        "博物館",
        "祭典",
        "エンタメ",
    ],

    "sports": [
        "スポーツ",
        "サッカー",
        "テニス",
        "スキー",
        "水泳",
        "陸上",
        "大会",
        "選手",
        "試合",
    ],
}


MAX_TOPICS = 3


def get_other_topic():
    """
    「その他」ジャンルを取得する。

    存在しなければ作成する。
    既存のジャンルが非表示なら有効化する。
    """

    topic, _ = Topic.objects.get_or_create(
        slug="other",
        defaults={
            "name": "その他",
            "is_active": True,
        },
    )

    if (
        topic.name != "その他"
        or not topic.is_active
    ):

        topic.name = "その他"
        topic.is_active = True

        topic.save(
            update_fields=[
                "name",
                "is_active",
            ]
        )

    return topic


def classify_japanese_text(
    title,
    summary="",
):
    """
    日本語記事をキーワードベースで分類する。

    OpenAI APIは使用しない。
    """

    text = (
        f"{title or ''} "
        f"{summary or ''}"
    ).lower()

    scores = {}

    for slug, keywords in TOPIC_KEYWORDS.items():

        score = 0

        for keyword in keywords:

            if keyword.lower() in text:
                score += 1

        if score > 0:
            scores[slug] = score

    ranked = sorted(
        scores,
        key=lambda slug: scores[slug],
        reverse=True,
    )

    return ranked[:MAX_TOPICS]


def assign_japanese_topics(article):
    """
    日本語記事にTopicを設定する。

    分類できなかった場合は「その他」にする。
    """

    slugs = classify_japanese_text(
        article.title_ja
        or article.title_original,
        article.summary_ja
        or article.summary_original,
    )

    if not slugs:

        other_topic = get_other_topic()

        article.topics.set(
            [other_topic]
        )

        return [other_topic]

    topics = list(
        Topic.objects.filter(
            slug__in=slugs,
            is_active=True,
        )
    )

    # キーワードに対応するTopicが
    # DBに存在しない場合も「その他」にする。

    if not topics:

        other_topic = get_other_topic()

        article.topics.set(
            [other_topic]
        )

        return [other_topic]

    article.topics.set(
        topics
    )

    return topics