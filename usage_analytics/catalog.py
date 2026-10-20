"""
Yapp のアプリ一覧 (アクセス解析用)。

URLの先頭 (/news/ など) からアプリを判定する。
ここにない新しいアプリも、先頭のパスをそのままキーにして
自動で集計されるので、公開したらすぐ解析ページに出てくる。
名前と絵文字を付けたいときだけ、ここに1行足す。
"""

# 色は解析ページのグラフ用 (CVDチェック済みの順番で割り当て)。
APP_CATALOG = {
    "news": {"name": "Swiss News", "emoji": "📰", "color": 1},
    "washoku": {"name": "スイスで和食", "emoji": "🍙", "color": 2},
    "outings": {"name": "おでかけ", "emoji": "⛰️", "color": 3},
    "portal": {"name": "Yappトップ", "emoji": "🏠", "color": 4},
    "support": {"name": "サポート", "emoji": "💝", "color": 5},
    "recipes": {"name": "料理・レシピ", "emoji": "🍳", "color": 0},
    "feeding": {"name": "離乳食記録", "emoji": "🍼", "color": 0},
    "vaccination": {"name": "ワクチン記録", "emoji": "💉", "color": 0},
    "games": {"name": "ミニゲーム", "emoji": "🎮", "color": 0},
    "colorcheck": {"name": "色判定", "emoji": "🎨", "color": 0},
    "travel": {"name": "旅行", "emoji": "✈️", "color": 0},
    "board": {"name": "お知らせ", "emoji": "📌", "color": 0},
    "chat": {"name": "チャット", "emoji": "💬", "color": 0},
    "events": {"name": "日程調整", "emoji": "📅", "color": 0},
    "swiss-board": {"name": "スイス掲示板", "emoji": "🗒️", "color": 0},
}

# ポータル (ログイン・アカウント系) にまとめるパス
PORTAL_PREFIXES = (
    "signup",
    "setup",
    "apps",
    "account",
    "accounts",
    "password",
)

# 記録しないパス (管理画面・解析ページ自身・内部API・静的ファイル)
SKIP_PREFIXES = (
    "/admin/",
    "/analytics/",
    "/static/",
    "/media/",
    "/news/internal/",
    "/news/push/",
    "/manifest.webmanifest",
    "/service-worker.js",
    "/favicon.ico",
    "/robots.txt",
)


def should_track_path(path):

    return not path.startswith(SKIP_PREFIXES)


def app_for_path(path):

    first = path.strip("/").split("/", 1)[0]

    if not first or first in PORTAL_PREFIXES:
        return "portal"

    return first[:40]


def app_info(app_key):

    info = APP_CATALOG.get(app_key)

    if info:
        return {"key": app_key, **info}

    return {
        "key": app_key,
        "name": f"/{app_key}/",
        "emoji": "🧩",
        "color": 0,
    }
