from django import template


register = template.Library()


# ほとんど使わないアプリ。Admin では折りたたんでおき、必要なときだけ開く
RARE_APPS = ["board", "chat", "feeding", "recipes", "vaccination", "core", "axes"]


# スイスで和食は項目が多いので、用途ごとに分けて並べる (モデル名, この順に並ぶ)
WASHOKU_SECTIONS = [
    ("スイスで和食：コミュニティ", [
        "ColumnPost", "PollPost", "QuestionComment", "StoreReview", "ReviewPost", "LinkPost",
        "PollSuggestion", "MemberPhoto", "CommentReport", "Feedback",
    ]),
    ("スイスで和食：レシピ・食材・お店", [
        "Recipe", "Ingredient", "Substitute", "Store", "MoodTag", "ShopType",
    ]),
    ("スイスで和食：HOME・お知らせ・設定", [
        "Announcement", "DisplaySettings", "Stamp", "PushSubscription",
    ]),
]

WASHOKU_REST = "スイスで和食：まとめて見る・記録"

# まとめて検索では出さない一覧 (種類ごとの一覧と同じものが並ぶため)
SEARCH_SKIP = {("washoku", "Post")}

# まとめて見る画面は、種類ごとの画面と区別できる名前にする
WASHOKU_RENAME = {
    "Post": "すべての投稿（まとめて）",
    "Comment": "すべてのコメント（まとめて）",
}


def split_washoku(app):

    models = {model["object_name"]: model for model in app["models"]}

    for name, label in WASHOKU_RENAME.items():
        if name in models:
            models[name] = {**models[name], "name": label}

    sections = []
    used = set()

    for title, names in WASHOKU_SECTIONS + [(WASHOKU_REST, None)]:
        if names is None:
            names = [name for name in models if name not in used]
        picked = [models[name] for name in names if name in models and name not in used]
        used.update(model["object_name"] for model in picked)
        if picked:
            sections.append({**app, "name": title, "models": picked})

    return sections


@register.simple_tag
def yapp_split_apps(app_list):
    """並び順はそのままで、ほとんど使わないアプリだけを分ける。スイスで和食は用途ごとに分ける。"""

    # いちばんよく使うスイスで和食を先頭に
    main = []

    for app in app_list:
        if app["app_label"] == "washoku":
            main = split_washoku(app) + main
        elif app["app_label"] not in RARE_APPS:
            main.append(app)

    return {
        "main": main,
        "rare": [app for app in app_list if app["app_label"] in RARE_APPS],
    }
