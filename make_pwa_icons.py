from pathlib import Path

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
)


OUTPUT_DIR = Path(
    "static/pwa"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def make_icon(size, filename):

    image = Image.new(
        "RGB",
        (size, size),
        "#6577B6",
    )

    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(
        "C:/Windows/Fonts/arialbd.ttf",
        int(size * 0.56),
    )

    draw.text(
        (size / 2, size / 2),
        "Y",
        fill="#FFFFFF",
        font=font,
        anchor="mm",
    )

    image.save(
        OUTPUT_DIR / filename
    )


make_icon(
    192,
    "icon-192.png",
)

make_icon(
    512,
    "icon-512.png",
)

make_icon(
    512,
    "icon-maskable.png",
)

make_icon(
    180,
    "apple-touch-icon.png",
)

print(
    "PWA icons created."
)