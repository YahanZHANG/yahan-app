"""
流入元 (どこから来たか) の分類。

訪問の最初のページの Referer と utm_* から
「検索」「SNS」「メッセージ」「他サイト」「キャンペーン」「直接」に分ける。
"""

SOURCE_TYPES = {
    "search": {"name": "検索エンジン", "short": "検索", "color": 1},
    "social": {"name": "SNS", "short": "SNS", "color": 2},
    "messaging": {"name": "メッセージ・メール", "short": "メッセージ", "color": 3},
    "campaign": {"name": "キャンペーン (utm付きリンク)", "short": "キャンペーン", "color": 4},
    "referral": {"name": "他のサイト", "short": "他サイト", "color": 5},
    "direct": {"name": "直接 (ブックマーク・ホーム画面・URL入力)", "short": "直接", "color": 0, "css": "s0"},
    "unknown": {"name": "記録なし (以前のデータ)", "short": "記録なし", "color": 0, "css": "s9"},
}

SOURCE_ORDER = list(SOURCE_TYPES)

# (ホスト名に含まれる文字列, 種類, 表示名)
KNOWN_HOSTS = (
    ("android.gm", "messaging", "Gmail"),
    ("mail.", "messaging", "メール"),
    ("jp.naver.line", "messaging", "LINE"),
    ("line.naver", "messaging", "LINE"),
    ("google.", "search", "Google"),
    ("bing.com", "search", "Bing"),
    ("duckduckgo", "search", "DuckDuckGo"),
    ("yahoo.", "search", "Yahoo!"),
    ("ecosia", "search", "Ecosia"),
    ("search.brave", "search", "Brave Search"),
    ("qwant", "search", "Qwant"),
    ("yandex", "search", "Yandex"),
    ("baidu", "search", "Baidu"),
    ("naver", "search", "Naver"),
    ("chatgpt.com", "referral", "ChatGPT"),
    ("perplexity", "referral", "Perplexity"),
    ("claude.ai", "referral", "Claude"),
    ("facebook", "social", "Facebook"),
    ("fb.me", "social", "Facebook"),
    ("instagram", "social", "Instagram"),
    ("threads.", "social", "Threads"),
    ("t.co", "social", "X (Twitter)"),
    ("twitter", "social", "X (Twitter)"),
    ("x.com", "social", "X (Twitter)"),
    ("reddit", "social", "Reddit"),
    ("linkedin", "social", "LinkedIn"),
    ("lnkd.in", "social", "LinkedIn"),
    ("youtube", "social", "YouTube"),
    ("tiktok", "social", "TikTok"),
    ("pinterest", "social", "Pinterest"),
    ("bsky", "social", "Bluesky"),
    ("mastodon", "social", "Mastodon"),
    ("note.com", "social", "note"),
    ("ameblo", "social", "Ameba"),
    ("line.me", "messaging", "LINE"),
    ("whatsapp", "messaging", "WhatsApp"),
    ("telegram", "messaging", "Telegram"),
    ("t.me", "messaging", "Telegram"),
    ("messenger", "messaging", "Messenger"),
    ("discord", "messaging", "Discord"),
    ("slack", "messaging", "Slack"),
    ("outlook", "messaging", "メール"),
)

def _host_matches(host, needle):

    # "google." は google.com / google.co.jp / news.google.com に一致
    if needle.endswith("."):
        return ("." + needle) in ("." + host)

    # "t.co" は t.co とそのサブドメインだけ (reddit.com に一致させない)
    if "." in needle:
        return (
            host == needle
            or host.endswith("." + needle)
            or host.startswith(needle + ".")
        )

    return needle in host


def classify_source(referrer_host, utm_source="", own_hosts=()):
    """
    (種類, 表示名) を返す。表示名は「Google」「LINE」「instagram」など。
    """

    utm_source = (utm_source or "").strip()
    host = (referrer_host or "").lower().strip(".")

    if host.startswith("www."):
        host = host[4:]

    if utm_source:
        return "campaign", utm_source[:120]

    if not host or host in own_hosts:
        return "direct", "直接"

    for needle, source_type, label in KNOWN_HOSTS:
        if _host_matches(host, needle):
            return source_type, label

    return "referral", host[:120]


def source_info(source_type):

    if source_type not in SOURCE_TYPES:
        source_type = "unknown"

    info = SOURCE_TYPES[source_type]

    return {
        "key": source_type,
        "css": info.get("css") or f"s{info['color']}",
        **info,
    }
