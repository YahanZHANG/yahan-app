"""
プロフィールのイラスト (写真を出したくない人向け)。
背景色・肌の色・髪型・髪の色・眼鏡・口・ほっぺ/ひげ を選んで組み合わせる。
SVG はサーバーで作るので、どの画面でも同じ絵になる。
"""

from django.utils.html import escape


BACKGROUNDS = [
    ("sky", "そら", "#BFE0F2"),
    ("mint", "ミント", "#C9EAD3"),
    ("peach", "ピーチ", "#FAD6C2"),
    ("lemon", "レモン", "#F6E7A6"),
    ("lilac", "ラベンダー", "#DCD2F2"),
    ("rose", "ローズ", "#F5CCD8"),
    ("cloud", "グレー", "#E1E5EA"),
    ("red", "スイスレッド", "#E45B63"),
]
SKINS = [
    ("1", "明るめ", "#FCE5D3"),
    ("2", "ふつう", "#F2C9A4"),
    ("3", "小麦色", "#D9A378"),
    ("4", "濃いめ", "#A8704A"),
]
HAIRS = [
    ("mid", "ミディアム"),
    ("short", "ショート"),
    ("side", "七三"),
    ("bob", "ボブ"),
    ("long", "ロング"),
    ("bun", "おだんご"),
    ("curly", "くるくる"),
    ("cap", "ニット帽"),
    ("none", "ぼうず"),
]
HAIR_COLORS = [
    ("black", "黒", "#2B2522"),
    ("dark", "こげ茶", "#4E3426"),
    ("brown", "茶色", "#8A5A3A"),
    ("blond", "金色", "#D9B266"),
    ("grey", "グレー", "#A3A7AD"),
]
GLASSES = [
    ("none", "なし"),
    ("round", "丸めがね"),
    ("square", "四角めがね"),
    ("sun", "サングラス"),
]
MOUTHS = [
    ("smile", "にっこり"),
    ("grin", "わはは"),
    ("calm", "おだやか"),
]
EXTRAS = [
    ("none", "なし"),
    ("cheeks", "ほっぺ"),
    ("beard", "ひげ"),
    ("mustache", "口ひげ"),
]

PARTS = {
    "bg": BACKGROUNDS,
    "skin": SKINS,
    "hair": HAIRS,
    "hair_color": HAIR_COLORS,
    "glasses": GLASSES,
    "mouth": MOUTHS,
    "extra": EXTRAS,
}
PART_LABELS = [
    ("bg", "背景"),
    ("skin", "肌の色"),
    ("hair", "髪型"),
    ("hair_color", "髪の色"),
    ("glasses", "めがね"),
    ("mouth", "口"),
    ("extra", "ほっぺ・ひげ"),
]
DEFAULT = {"bg": "sky", "skin": "2", "hair": "mid", "hair_color": "black", "glasses": "none", "mouth": "smile", "extra": "none"}

SHIRTS = {
    "sky": "#3C6E91", "mint": "#3F7F5B", "peach": "#B5643E", "lemon": "#8C7A2E",
    "lilac": "#6A55A0", "rose": "#A84A64", "cloud": "#56606C", "red": "#FFFFFF",
}


def clean(parts):
    """保存・表示用に、知らない値を外して足りない値を補う"""

    parts = parts if isinstance(parts, dict) else {}
    result = {}
    for key, options in PARTS.items():
        value = str(parts.get(key, ""))
        result[key] = value if value in {option[0] for option in options} else DEFAULT[key]
    return result


def from_post(data):
    return clean({key: data.get(f"av_{key}", "") for key in PARTS})


def _color(options, key):
    for option in options:
        if option[0] == key:
            return option[2]
    return options[0][2]


def _hair(style, color):
    """(顔より後ろの髪, 顔より前の髪)"""

    if style == "mid":
        back = f'<path d="M21 60 C18 29 34 18 50 18 C66 18 82 29 79 60 C79 67 76 69 72 69 L28 69 C24 69 21 67 21 60Z" fill="{color}"/>'
        front = f'<path d="M25 53 C24 31 38 23 50 23 C62 23 76 31 75 53 C71 46 65 40 59 37 C52 43 39 46 25 53Z" fill="{color}"/>'
        return back, front
    if style == "short":
        return "", f'<path d="M25 55 C22 30 37 21 50 21 C64 21 79 30 75 55 C72 43 64 35 50 35 C37 35 29 42 25 55Z" fill="{color}"/>'
    if style == "side":
        return "", f'<path d="M24 56 C21 29 39 19 54 20 C70 21 80 33 76 56 C73 44 66 33 56 33 C48 41 36 45 24 56Z" fill="{color}"/>'
    if style == "bob":
        back = f'<path d="M21 58 C18 29 34 19 50 19 C66 19 82 29 79 58 L79 76 C72 78 68 76 66 72 L34 72 C32 76 28 78 21 76Z" fill="{color}"/>'
        front = f'<path d="M25 52 C25 32 37 25 50 25 C63 25 75 32 75 52 C69 45 63 37 56 36 C50 42 36 46 25 52Z" fill="{color}"/>'
        return back, front
    if style == "long":
        back = f'<path d="M20 58 C17 28 34 18 50 18 C66 18 83 28 80 58 L82 92 L18 92Z" fill="{color}"/>'
        front = f'<path d="M25 54 C24 32 37 24 50 24 C63 24 76 32 75 54 C70 44 60 36 50 36 C40 36 30 44 25 54Z" fill="{color}"/>'
        return back, front
    if style == "bun":
        back = f'<circle cx="50" cy="15" r="10" fill="{color}"/>'
        front = f'<path d="M25 54 C23 31 37 23 50 23 C63 23 77 31 75 54 C71 43 62 35 50 35 C38 35 29 43 25 54Z" fill="{color}"/>'
        return back, front
    if style == "curly":
        circles = "".join(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'
            for x, y, r in [(28, 46, 8), (32, 33, 9), (42, 25, 9), (55, 24, 9), (67, 30, 9), (73, 43, 8), (50, 31, 8)]
        )
        return "", circles
    if style == "cap":
        front = (
            '<path d="M24 50 C24 28 37 18 50 18 C63 18 76 28 76 50Z" fill="#D94A4F"/>'
            '<rect x="22" y="44" width="56" height="9" rx="4.5" fill="#B83A40"/>'
            '<circle cx="50" cy="16" r="5" fill="#F3F3F3"/>'
        )
        return "", front
    return "", ""


def _glasses(kind):
    if kind == "round":
        return (
            '<g fill="none" stroke="#2F2F2F" stroke-width="2">'
            '<circle cx="41" cy="57" r="6.5"/><circle cx="59" cy="57" r="6.5"/><path d="M47.5 57 L52.5 57"/></g>'
        )
    if kind == "square":
        return (
            '<g fill="none" stroke="#2F2F2F" stroke-width="2">'
            '<rect x="33.5" y="51.5" width="14" height="11" rx="2"/><rect x="52.5" y="51.5" width="14" height="11" rx="2"/>'
            '<path d="M47.5 56 L52.5 56"/></g>'
        )
    if kind == "sun":
        return (
            '<g fill="#232323" stroke="#232323" stroke-width="1.5">'
            '<rect x="33" y="52" width="15" height="10" rx="4"/><rect x="52" y="52" width="15" height="10" rx="4"/>'
            '<path d="M48 55 L52 55" fill="none"/></g>'
        )
    return ""


def _mouth(kind):
    if kind == "grin":
        return '<path d="M42 67 Q50 78 58 67Z" fill="#FFFFFF" stroke="#7A3B2E" stroke-width="1.8" stroke-linejoin="round"/>'
    if kind == "calm":
        return '<path d="M45 70 Q50 72 55 70" fill="none" stroke="#7A3B2E" stroke-width="2" stroke-linecap="round"/>'
    return '<path d="M43 68 Q50 75 57 68" fill="none" stroke="#7A3B2E" stroke-width="2.2" stroke-linecap="round"/>'


def _extra(kind, hair_color):
    if kind == "cheeks":
        return '<ellipse cx="35" cy="65" rx="4.5" ry="3" fill="#F28B95" opacity=".55"/><ellipse cx="65" cy="65" rx="4.5" ry="3" fill="#F28B95" opacity=".55"/>'
    if kind == "beard":
        return f'<path d="M27 60 C28 80 40 87 50 87 C60 87 72 80 73 60 C70 70 63 75 57 75 C55 72 45 72 43 75 C37 75 30 70 27 60Z" fill="{hair_color}"/>'
    if kind == "mustache":
        return f'<path d="M41 65 C45 61 49 63 50 65 C51 63 55 61 59 65 C55 67 52 67 50 66 C48 67 45 67 41 65Z" fill="{hair_color}"/>'
    return ""


def svg(parts, title=""):
    parts = clean(parts)
    bg = _color(BACKGROUNDS, parts["bg"])
    skin = _color(SKINS, parts["skin"])
    hair_color = _color(HAIR_COLORS, parts["hair_color"])
    shirt = SHIRTS.get(parts["bg"], "#56606C")
    back, front = _hair(parts["hair"], hair_color)
    label = f"<title>{escape(title)}</title>" if title else ""
    brow = "" if parts["glasses"] == "sun" else (
        f'<path d="M36 49 Q41 46.5 46 49 M54 49 Q59 46.5 64 49" fill="none" stroke="{hair_color}" stroke-width="1.5" stroke-linecap="round" opacity=".7"/>'
    )
    eyes = "" if parts["glasses"] == "sun" else '<circle cx="41" cy="57" r="2.7" fill="#2B2522"/><circle cx="59" cy="57" r="2.7" fill="#2B2522"/>'
    return (
        f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" role="img" aria-hidden="true">{label}'
        f'<rect width="100" height="100" fill="{bg}"/>'
        f"{back}"
        f'<path d="M14 100 C16 82 32 76 50 76 C68 76 84 82 86 100Z" fill="{shirt}"/>'
        f'<rect x="43" y="70" width="14" height="10" fill="{skin}"/>'
        f'<circle cx="26" cy="59" r="4.5" fill="{skin}"/><circle cx="74" cy="59" r="4.5" fill="{skin}"/>'
        f'<ellipse cx="50" cy="57" rx="24" ry="26" fill="{skin}"/>'
        f"{_extra(parts['extra'], hair_color)}{brow}{eyes}{_mouth(parts['mouth'])}{front}{_glasses(parts['glasses'])}"
        "</svg>"
    )


def choices_for_editor(current):
    """編集画面で並べる選択肢 (それぞれ、その部分だけ変えた絵つき)"""

    current = clean(current)
    groups = []
    for key, label in PART_LABELS:
        options = []
        for option in PARTS[key]:
            preview = dict(current, **{key: option[0]})
            options.append({"value": option[0], "label": option[1], "svg": svg(preview), "on": current[key] == option[0]})
        groups.append({"key": key, "label": label, "options": options})
    return groups
