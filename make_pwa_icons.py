"""
Yapp のアイコン (static/portal/yapp-icon.png) から
favicon・ホーム画面用アイコンを作り直すスクリプト。

    python make_pwa_icons.py
"""

from pathlib import Path

from PIL import Image


SOURCE = Path(
    "static/portal/yapp-icon.png"
)

OUTPUT_DIR = Path(
    "static/pwa"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# 元画像から角丸の正方形部分だけを切り出す
# (周りの透明な余白と影を落とす)
# =========================================================

source = Image.open(SOURCE).convert("RGBA")

solid = source.getchannel("A").point(
    lambda value: 255 if value > 240 else 0
)

left, top, right, bottom = solid.getbbox()

side = max(right - left, bottom - top)

center_x = (left + right) // 2
center_y = (top + bottom) // 2

tile = source.crop(
    (
        center_x - side // 2,
        center_y - side // 2,
        center_x - side // 2 + side,
        center_y - side // 2 + side,
    )
)


# 角丸の外側を埋めるための背景色 (アイコン下側の濃い青)
BACKGROUND = (12, 50, 130, 255)


def transparent(size):

    return tile.resize(
        (size, size),
        Image.LANCZOS,
    )


def opaque(size, scale=1.0):

    canvas = Image.new(
        "RGBA",
        (size, size),
        BACKGROUND,
    )

    inner = round(size * scale)

    # 少し拡大して、元画像の角丸を OS 側の角丸マスクの外に出す
    image = tile.resize(
        (inner, inner),
        Image.LANCZOS,
    )

    offset = (size - inner) // 2

    canvas.alpha_composite(
        image,
        (offset, offset),
    )

    return canvas.convert("RGB")


# ブラウザのタブ用 (透明背景)
transparent(32).save(OUTPUT_DIR / "favicon-32.png")

transparent(256).save(
    OUTPUT_DIR / "favicon.ico",
    sizes=[(16, 16), (32, 32), (48, 48)],
)

# Android / PC のインストール用 (透明背景)
transparent(192).save(OUTPUT_DIR / "icon-192.png")
transparent(512).save(OUTPUT_DIR / "icon-512.png")

# iPhone のホーム画面用 (iOS は透明部分を黒にするので不透明)
opaque(180, scale=1.06).save(OUTPUT_DIR / "apple-touch-icon.png")

# Android の maskable 用 (中央 80% の円に Y が収まるよう縮小)
opaque(512, scale=0.78).save(OUTPUT_DIR / "icon-maskable.png")


print(
    "PWA icons created."
)
