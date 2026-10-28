"""Yappトップの季節とイベントのデザイン。

日付（スイス時間）から自動で切り替える。イベントの期間中はイベント、
それ以外は季節のデザインになる。イベント同士が重なるときは、期間の短いほうを優先する。
新しいイベントを足すときは THEMES と event_ranges() の両方に書く。
"""

from datetime import date, timedelta


# particle: ヒーローに舞う飾りの動き
#   fall=上から落ちる / rise=下から上る / snow=雪 / petal=花びら
#   firework=花火 / rain=雨 / twinkle=星がまたたく / halloween=ハロウィン
# motif: 右下に大きく置く飾り
# sky: ヒーローの空の色 (上から下へ)
# accent: ボタンなどのテーマ色
THEMES = {
    # ---------------- イベント ----------------
    "newyear": {
        "name": "大晦日・お正月",
        "title": "新しい年も",
        "headline": "スイスで楽しもう。",
        "particle": "firework",
        "symbols": [""],
        "motif": ["🎍", "🌅", "🎍"],
        "sky": ("#0d1b3d", "#3a2a5e", "#f2945a"),
        "accent": "#c8102e",
    },
    "valentine": {
        "name": "バレンタイン",
        "title": "大切な人と",
        "headline": "甘いひとときを。",
        "particle": "rise",
        "symbols": ["❤", "💗", "🍫", "💕"],
        "motif": ["🍫", "💝", "🍫"],
        "sky": ("#4a1028", "#b23a6e", "#ffb3cf"),
        "accent": "#d63a6e",
    },
    "hinamatsuri": {
        "name": "ひな祭り",
        "title": "桃の花がほころぶ",
        "headline": "ひな祭りの季節に。",
        "particle": "petal",
        "symbols": [""],
        "motif": ["🎎", "🌸", "🍡"],
        "sky": ("#5b2a4e", "#d97a9e", "#ffe3ec"),
        "accent": "#e05a87",
    },
    "sakura": {
        "name": "卒業式・入学式",
        "title": "新しい春を",
        "headline": "スイスから応援。",
        "particle": "petal",
        "symbols": [""],
        "motif": ["🌸", "🎓", "🎒"],
        "sky": ("#3c4f8a", "#9fb6e8", "#ffd9e6"),
        "accent": "#d94f7f",
    },
    "easter": {
        "name": "イースター",
        "title": "イースターの春を",
        "headline": "スイスで楽しもう。",
        "particle": "fall",
        "symbols": ["🥚", "🌷", "🐣", "🌼"],
        "motif": ["🐰", "🥚", "🌷"],
        "sky": ("#2f6d5a", "#8fd0aa", "#fff2c4"),
        "accent": "#2f9466",
    },
    "sechselaeuten": {
        "name": "ゼクセロイテン（チューリッヒの雪だるま祭り）",
        "title": "雪だるまが燃えたら",
        "headline": "春がやってくる！",
        "particle": "rise",
        "symbols": ["✦", "•", "✧", "•"],
        "motif": ["⛄", "🔥", "🐎"],
        "sky": ("#1d2a4a", "#6b4a7a", "#ff9a4a"),
        "accent": "#e8642c",
    },
    "koinobori": {
        "name": "こどもの日・こいのぼり",
        "title": "こいのぼりが泳ぐ",
        "headline": "スイスの青空へ。",
        "particle": "fall",
        "symbols": ["🍃", "✦", "🍃"],
        "motif": ["🎏", "🎏"],
        "sky": ("#1b6fb5", "#6fc0f0", "#e6f7ff"),
        "accent": "#1f7ac4",
    },
    "tsuyu": {
        "name": "梅雨",
        "title": "雨の日も",
        "headline": "おうちで楽しもう。",
        "particle": "rain",
        "symbols": [""],
        "motif": ["☔", "🐸", "🐌"],
        "sky": ("#3c4a63", "#7a8aa6", "#c8d3e6"),
        "accent": "#6f5cc4",
    },
    "tanabata": {
        "name": "七夕",
        "title": "願いをこめて",
        "headline": "星に届け。",
        "particle": "twinkle",
        "symbols": ["✦", "✧", "⭐", "✦"],
        "motif": ["🎋", "🌌"],
        "sky": ("#070b2a", "#1b2560", "#3a2a6b"),
        "accent": "#d9952b",
    },
    "natsumatsuri": {
        "name": "夏祭り",
        "title": "夏祭りの夜を",
        "headline": "もっと楽しく。",
        "particle": "firework",
        "symbols": [""],
        "motif": ["🏮", "🍧", "🎐"],
        "sky": ("#0b1030", "#3a1f5c", "#c0436b"),
        "accent": "#e8442e",
    },
    "swissnational": {
        "name": "スイス建国記念日（8月1日）",
        "title": "スイスの誕生日を",
        "headline": "一緒にお祝い！",
        "particle": "firework",
        "symbols": [""],
        "motif": ["🎆", "🏮", "🎆"],
        "sky": ("#0e1a3a", "#5a1a2e", "#d42a2a"),
        "accent": "#d52b1e",
    },
    "koyo": {
        "name": "紅葉の季節",
        "title": "紅葉のスイスを",
        "headline": "歩いてみよう。",
        "particle": "fall",
        "symbols": ["🍁", "🍂", "🍁", "🍂"],
        "motif": ["🍁", "🥾", "🍂"],
        "sky": ("#5a2a12", "#c8662a", "#ffc56b"),
        "accent": "#c8572a",
    },
    "halloween": {
        "name": "ハロウィン",
        "title": "スイスの秋の夜を",
        "headline": "もっと楽しく。",
        "particle": "halloween",
        "symbols": ["🦇", "🍂", "🎃", "🍁", "👻", "🍂"],
        "motif": [],
        "sky": ("#17152e", "#5a2a50", "#f08a4b"),
        "accent": "#ff7439",
    },
    "blackfriday": {
        "name": "ブラックフライデー",
        "title": "ブラックフライデー",
        "headline": "お得を見逃さない！",
        "particle": "fall",
        "symbols": ["🏷️", "%", "🛍️", "%"],
        "motif": ["🛍️", "🏷️"],
        "sky": ("#000000", "#1c1c1c", "#3a3a3a"),
        "accent": "#e63946",
    },
    "christmas": {
        "name": "クリスマス",
        "title": "きらめく季節を",
        "headline": "スイスで楽しもう。",
        "particle": "snow",
        "symbols": ["❄", "•", "❅", "•", "❆", "•"],
        "motif": ["🎄", "🎁", "⛄"],
        "sky": ("#0a1a3a", "#1e3d6b", "#2b6a7a"),
        "accent": "#c62828",
    },
    # ---------------- 季節 ----------------
    "winter": {
        "name": "冬",
        "title": "雪の日も",
        "headline": "スイスを楽しもう。",
        "particle": "snow",
        "symbols": ["❄", "•", "❅", "•", "❆", "•"],
        "motif": ["⛷️", "☃️"],
        "sky": ("#2a4a7a", "#8fb5dd", "#eef5ff"),
        "accent": "#2f86c4",
    },
    "spring": {
        "name": "春",
        "title": "花ひらく季節を",
        "headline": "スイスで楽しもう。",
        "particle": "petal",
        "symbols": [""],
        "motif": ["🌷", "🌼", "🐝"],
        "sky": ("#4a8fd0", "#a8d8f0", "#fdf2d0"),
        "accent": "#3f9a55",
    },
    "early_summer": {
        "name": "初夏",
        "title": "風が気持ちいい",
        "headline": "初夏のスイスへ。",
        "particle": "fall",
        "symbols": ["🍃", "🌿", "🍃"],
        "motif": ["⛵", "🌿"],
        "sky": ("#2f8fd8", "#8fd3f5", "#e9fbff"),
        "accent": "#16a07a",
    },
    "midsummer": {
        "name": "猛暑",
        "title": "暑い夏こそ",
        "headline": "スイスの湖へ。",
        "particle": "rise",
        "symbols": ["✦", "•", "✧", "•"],
        "motif": ["☀️", "🍉", "🏊"],
        "sky": ("#ff7a00", "#ffb52e", "#fff1a8"),
        "accent": "#ea6a0a",
    },
    "autumn": {
        "name": "秋",
        "title": "実りの秋を",
        "headline": "スイスで楽しもう。",
        "particle": "fall",
        "symbols": ["🍇", "🌰", "🍂", "🍎"],
        "motif": ["🍇", "🌰"],
        "sky": ("#3a5a8a", "#d8a060", "#f5d48a"),
        "accent": "#b8662a",
    },
    "late_autumn": {
        "name": "晩秋",
        "title": "霧の朝も",
        "headline": "ぬくぬく過ごそう。",
        "particle": "fall",
        "symbols": ["🍂", "•", "🍂", "•"],
        "motif": ["☕", "🌰"],
        "sky": ("#4a5060", "#8a90a0", "#c8ccd6"),
        "accent": "#8a5a3a",
    },
}


def easter_sunday(year):
    """グレゴリオ暦のイースター（復活祭）の日曜日。"""

    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year, month, weekday, n):
    """その月の n 番目の曜日 (weekday: 月曜=0)。"""

    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def event_ranges(year):
    """その年のイベント期間 (key, 開始日, 終了日) の一覧。終了日も含む。"""

    easter = easter_sunday(year)
    sechselaeuten = nth_weekday(year, 4, 0, 3)  # 4月第3月曜
    black_friday = nth_weekday(year, 11, 3, 4) + timedelta(days=1)  # 11月第4木曜の翌日

    return [
        ("newyear", date(year, 1, 1), date(year, 1, 7)),
        ("newyear", date(year, 12, 31), date(year, 12, 31)),
        ("valentine", date(year, 2, 7), date(year, 2, 14)),
        ("hinamatsuri", date(year, 2, 24), date(year, 3, 3)),
        ("sakura", date(year, 3, 15), date(year, 4, 10)),
        ("easter", easter - timedelta(days=2), easter + timedelta(days=1)),
        ("sechselaeuten", sechselaeuten - timedelta(days=3), sechselaeuten),
        ("koinobori", date(year, 4, 25), date(year, 5, 5)),
        ("tsuyu", date(year, 6, 8), date(year, 6, 30)),
        ("tanabata", date(year, 7, 1), date(year, 7, 7)),
        ("natsumatsuri", date(year, 7, 15), date(year, 7, 27)),
        ("swissnational", date(year, 7, 28), date(year, 8, 1)),
        ("koyo", date(year, 10, 1), date(year, 10, 14)),
        ("halloween", date(year, 10, 15), date(year, 10, 31)),
        ("blackfriday", black_friday - timedelta(days=4), black_friday + timedelta(days=3)),
        ("christmas", date(year, 12, 1), date(year, 12, 26)),
    ]


def season_of(day):
    """イベントがない日の季節。"""

    if day.month in (12, 1, 2):
        return "winter"
    if day.month in (3, 4, 5):
        return "spring"
    if day.month in (6, 7):
        return "early_summer"
    if day.month == 8:
        return "midsummer"
    if day.month in (9, 10):
        return "autumn"
    return "late_autumn"


def theme_for(day):
    """その日のテーマ。イベント中ならイベント (短いものを優先)、なければ季節。"""

    current = [
        (end - start, key)
        for key, start, end in event_ranges(day.year)
        if start <= day <= end
    ]
    if current:
        return min(current)[1]
    return season_of(day)


def particles(theme_key, count=22):
    """ヒーローに舞う飾り。毎回同じ並びになるよう、乱数の種を固定する。"""

    import random

    theme = THEMES[theme_key]
    rng = random.Random(theme_key)
    symbols = theme["symbols"]
    return [
        {
            "symbol": symbols[index % len(symbols)],
            "left": rng.randint(0, 100),
            "top": rng.randint(5, 70),
            "size": rng.randint(12, 34),
            "delay": round(rng.uniform(0, 12), 1),
            "duration": round(rng.uniform(9, 18), 1),
            "drift": rng.randint(-60, 60),
        }
        for index in range(count)
    ]


def accent_shadow(hex_color, alpha=0.38):
    """テーマ色からボタンの影の色を作る。"""

    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha})"
