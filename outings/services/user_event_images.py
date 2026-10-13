
from io import BytesIO

from django.core.exceptions import ValidationError
from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)


MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_INPUT_PIXELS = 12_000_000
MAX_OUTPUT_SIZE = 1600

SUPPORTED_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP",
}


def process_user_event_image(uploaded_file):

    if uploaded_file.size > MAX_FILE_SIZE:
        raise ValidationError(
            "画像は5MB以下にしてください。"
        )

    try:
        uploaded_file.seek(0)

        with Image.open(uploaded_file) as image:

            if image.format not in SUPPORTED_FORMATS:
                raise ValidationError(
                    "JPG・PNG・WebP形式のみ使用できます。"
                )

            width, height = image.size

            if (
                width <= 0
                or height <= 0
                or width * height > MAX_INPUT_PIXELS
            ):
                raise ValidationError(
                    "画像の画素数が上限を超えています。"
                )

            image = ImageOps.exif_transpose(
                image
            )

            image.thumbnail(
                (
                    MAX_OUTPUT_SIZE,
                    MAX_OUTPUT_SIZE,
                ),
                Image.Resampling.LANCZOS,
            )

            # Convert and discard original EXIF metadata.
            image = image.convert("RGB")

            output = BytesIO()

            image.save(
                output,
                format="WEBP",
                quality=82,
                method=6,
            )

            output.seek(0)

            return output

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as error:

        raise ValidationError(
            "画像を正常に読み込めませんでした。"
        ) from error
