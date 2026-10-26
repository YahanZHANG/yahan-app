from django import template
from django.urls import NoReverseMatch, reverse


register = template.Library()


# =========================================================
# Admin のトップ: アプリの並びと見せ方
# =========================================================

# いつも使うアプリ (開いた状態で上に出す)
MAIN_APPS = ["washoku", "news", "portal", "auth"]

# ほとんど使わないアプリ (まとめて1つに折りたたむ)
RARE_APPS = ["board", "chat", "feeding", "recipes", "vaccination", "core"]

APP_TITLES = {
    "washoku": ("🍙", "スイスで和食"),
    "news": ("📰", "Swiss News"),
    "portal": ("🏠", "Yapp"),
    "auth": ("👤", "ユーザー・権限"),
    "outings": ("⛰️", "おでかけ"),
    "usage_analytics": ("📊", "アクセス解析の記録"),
    "swiss_board": ("📌", "スイス掲示板"),
    "axes": ("🔐", "ログイン失敗の記録"),
    "board": ("📋", "Board"),
    "chat": ("💬", "Chat"),
    "feeding": ("🍼", "Feeding"),
    "recipes": ("🥘", "Recipes"),
    "vaccination": ("💉", "Vaccination"),
    "core": ("🧳", "旅行管理アプリ"),
}

# 和食はモデルが多いので、使う場面ごとに分ける
WASHOKU_GROUPS = [
    ("みんなの声", ["Comment", "Post", "MemberPhoto", "Feedback", "PollSuggestion", "PollVote", "PollAnswer", "CommentReport"]),
    ("レシピ・食材・お店", ["Recipe", "Ingredient", "Substitute", "Store", "ShopType", "MoodTag"]),
    ("お知らせ・表示", ["Announcement", "DisplaySettings", "Stamp", "Notification", "PushSubscription"]),
    ("会員・家族", ["Household", "HouseholdInvite", "RecipeRating"]),
]

NEWS_GROUPS = [
    ("届いたもの", ["NewsFeedback", "SupportRequest"]),
    ("記事・お知らせ", ["NewsAnnouncement", "Article", "NewsSource", "Topic"]),
    ("読者の設定", ["NewsPreference", "Favorite", "NewsPushSubscription"]),
]

MODEL_GROUPS = {
    "washoku": WASHOKU_GROUPS,
    "news": NEWS_GROUPS,
}


def _attention_by_url(admin_attention):
    """対応待ちの件数を、一覧ページのURLごとに足し合わせる。"""

    counts = {}

    for group in (admin_attention or {}).get("groups", []):
        for item in group["items"]:
            base = item["url"].split("?", 1)[0]
            counts[base] = counts.get(base, 0) + item["count"]

    return counts


def _app_card(app, counts):

    label = app["app_label"]
    emoji, title = APP_TITLES.get(label, ("📁", app["name"]))

    models = []
    for model in app["models"]:
        model = dict(model)
        model["pending"] = counts.get(model.get("admin_url") or "", 0)
        models.append(model)

    groups = []
    rules = MODEL_GROUPS.get(label)

    if rules:
        by_name = {model["object_name"]: model for model in models}
        used = set()
        for group_title, names in rules:
            rows = [by_name[name] for name in names if name in by_name]
            used.update(model["object_name"] for model in rows)
            if rows:
                groups.append({"title": group_title, "models": rows})
        rest = [model for model in models if model["object_name"] not in used]
        if rest:
            groups.append({"title": "その他", "models": rest})
    else:
        groups.append({"title": "", "models": models})

    return {
        "label": label,
        "emoji": emoji,
        "title": title,
        "url": app["app_url"],
        "groups": groups,
        "count": len(models),
        "pending": sum(model["pending"] for model in models),
    }


@register.simple_tag
def yapp_admin_sections(app_list, admin_attention=None):

    counts = _attention_by_url(admin_attention)
    cards = {app["app_label"]: _app_card(app, counts) for app in app_list}

    main = [cards.pop(label) for label in MAIN_APPS if label in cards]
    rare = [cards.pop(label) for label in RARE_APPS if label in cards]
    other = sorted(cards.values(), key=lambda card: (-card["pending"], card["title"]))

    return {"main": main, "other": other, "rare": rare}


def _changelist(name, query=""):
    try:
        return reverse(name) + (f"?{query}" if query else "")
    except NoReverseMatch:
        return ""


@register.simple_tag
def yapp_admin_inbox(admin_attention=None):
    """
    トップに大きく出す「いつも見るところ」。
    0件でも出して、空なら ✓ にする。
    """

    attention = admin_attention or {}
    found = {}

    for group in attention.get("groups", []):
        for item in group["items"]:
            found[(group["app"], item["label"])] = item

    def tile(tone, emoji, title, app, label, url_name, query):
        item = found.get((app, label))
        return {
            "tone": tone,
            "emoji": emoji,
            "title": title,
            "count": item["count"] if item else 0,
            "url": item["url"] if item else _changelist(url_name, query),
        }

    washoku = next((group for group in attention.get("groups", []) if group["app"] == "スイスで和食"), None)
    washoku_items = [item for item in (washoku or {}).get("items", []) if item["label"] != "質問箱"]

    tiles = [
        {
            "tone": "washoku",
            "emoji": "🍙",
            "title": "和食の対応待ち",
            "count": sum(item["count"] for item in washoku_items),
            "url": washoku_items[0]["url"] if washoku_items else _changelist("admin:washoku_comment_changelist"),
            "chips": washoku_items,
        },
        tile("support", "💌", "Yapp 応援メッセージ", "Swiss News", "応援の問い合わせ", "admin:news_supportrequest_changelist", "is_read__exact=0"),
        tile("news", "📰", "Swiss News 質問箱", "Swiss News", "ご意見・ご要望", "admin:news_newsfeedback_changelist", "is_read__exact=0"),
        tile("question", "💬", "和食 質問箱", "スイスで和食", "質問箱", "admin:washoku_feedback_changelist", "is_read__exact=0"),
    ]

    shown = {("Swiss News", "応援の問い合わせ"), ("Swiss News", "ご意見・ご要望")}
    others = [
        dict(item, app=group["app"])
        for group in attention.get("groups", [])
        if group["app"] != "スイスで和食"
        for item in group["items"]
        if (group["app"], item["label"]) not in shown
    ]

    return {"tiles": tiles, "others": others}


@register.simple_tag
def yapp_sidebar_apps(available_apps):
    """
    一覧ページ左のメニュー用。
    いつも使うアプリを上に、残りは「ほかのアプリ」にまとめる。
    """

    def named(app):
        emoji, title = APP_TITLES.get(app["app_label"], ("", app["name"]))
        return dict(app, name=f"{emoji} {title}".strip())

    apps = {app["app_label"]: named(app) for app in available_apps}

    main = [apps.pop(label) for label in MAIN_APPS if label in apps]
    rare = [apps.pop(label) for label in RARE_APPS if label in apps]
    rest = sorted(apps.values(), key=lambda app: app["name"]) + rare

    return {"main": main, "rest": rest}
