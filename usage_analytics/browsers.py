"""
どこで開いたか (ブラウザ / アプリ内ブラウザ) の判定。

LINE・Facebook・Instagram などのアプリの中で開いたページは、
Safari や Chrome とは別に cookie を持つ (消されることも多い) ので、
同じ人が別の人として数えられやすい。それを解析ページで見えるようにする。
"""

# (User-Agent に含まれる文字列, キー) 上から順に判定
IN_APP_PATTERNS = (
    ("Line/", "line"),
    ("FBAN/Messenger", "messenger"),
    ("FB_IAB/MESSENGER", "messenger"),
    ("Instagram", "instagram"),
    ("FBAN", "facebook"),
    ("FBAV", "facebook"),
    ("FB_IAB", "facebook"),
    ("Twitter", "x"),
    ("TikTok", "tiktok"),
    ("musical_ly", "tiktok"),
    ("BytedanceWebview", "tiktok"),
    ("MicroMessenger", "wechat"),
    ("Snapchat", "snapchat"),
    ("Pinterest", "pinterest"),
    ("GSA/", "google_app"),
)

BROWSER_PATTERNS = (
    ("Edg", "edge"),
    ("SamsungBrowser", "samsung"),
    ("FxiOS", "firefox"),
    ("Firefox", "firefox"),
    ("CriOS", "chrome"),
    ("Chrome", "chrome"),
    ("Safari", "safari"),
)

BROWSERS = {
    "line": {"name": "LINE内", "in_app": True},
    "facebook": {"name": "Facebook内", "in_app": True},
    "instagram": {"name": "Instagram内", "in_app": True},
    "messenger": {"name": "Messenger内", "in_app": True},
    "x": {"name": "X (Twitter)内", "in_app": True},
    "tiktok": {"name": "TikTok内", "in_app": True},
    "wechat": {"name": "WeChat内", "in_app": True},
    "snapchat": {"name": "Snapchat内", "in_app": True},
    "pinterest": {"name": "Pinterest内", "in_app": True},
    "google_app": {"name": "Googleアプリ内", "in_app": True},
    "other_app": {"name": "その他のアプリ内", "in_app": True},
    "ios_app": {"name": "ホーム画面アプリ / その他のアプリ内 (iPhone)", "in_app": True},
    "safari": {"name": "Safari", "in_app": False},
    "chrome": {"name": "Chrome", "in_app": False},
    "firefox": {"name": "Firefox", "in_app": False},
    "edge": {"name": "Edge", "in_app": False},
    "samsung": {"name": "Samsungブラウザ", "in_app": False},
    "other": {"name": "その他のブラウザ", "in_app": False},
    "": {"name": "記録なし (以前のデータ)", "in_app": False},
}


def detect_browser(user_agent):

    for needle, key in IN_APP_PATTERNS:
        if needle in user_agent:
            return key

    # Android のアプリ内 WebView は "; wv)" が付く
    if "; wv)" in user_agent:
        return "other_app"

    # iPhone で "Safari/" が付かないのは、ホーム画面に追加したアプリか、
    # 名前の分からないアプリの中 (どちらかは区別できない)
    if ("iPhone" in user_agent or "iPad" in user_agent) and "Safari/" not in user_agent:
        return "ios_app"

    for needle, key in BROWSER_PATTERNS:
        if needle in user_agent:
            return key

    return "other"


def browser_info(key):

    info = BROWSERS.get(key, BROWSERS["other"])

    return {"key": key, **info}
