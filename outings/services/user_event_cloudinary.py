
import os
from urllib.parse import urlparse, unquote

import requests

from django.core.exceptions import ValidationError


def get_cloudinary_settings():

    cloud_name = os.getenv(
        "CLOUDINARY_CLOUD_NAME", ""
    )

    api_key = os.getenv(
        "CLOUDINARY_API_KEY", ""
    )

    api_secret = os.getenv(
        "CLOUDINARY_API_SECRET", ""
    )

    # Also support the common CLOUDINARY_URL format:
    # cloudinary://API_KEY:API_SECRET@CLOUD_NAME

    cloudinary_url = os.getenv(
        "CLOUDINARY_URL", ""
    )

    if cloudinary_url and not all(
        [cloud_name, api_key, api_secret]
    ):

        parsed = urlparse(cloudinary_url)

        if parsed.scheme == "cloudinary":
            cloud_name = cloud_name or parsed.hostname or ""
            api_key = api_key or unquote(parsed.username or "")
            api_secret = api_secret or unquote(parsed.password or "")

    if not all([cloud_name, api_key, api_secret]):
        raise ValidationError(
            "画像保存サービスが設定されていません。"
        )

    return cloud_name, api_key, api_secret


def upload_user_event_photo(image_file):

    cloud_name, api_key, api_secret = (
        get_cloudinary_settings()
    )

    image_file.seek(0)

    try:

        response = requests.post(
            (
                "https://api.cloudinary.com/v1_1/"
                f"{cloud_name}/image/upload"
            ),
            auth=(api_key, api_secret),
            files={
                "file": (
                    "event_photo.webp",
                    image_file,
                    "image/webp",
                )
            },
            data={
                "folder": "yapp/outings/member-events",
                "resource_type": "image",
                "overwrite": "false",
            },
            timeout=60,
        )

        response.raise_for_status()

        image_url = response.json().get(
            "secure_url", ""
        )

    except (
        requests.RequestException,
        ValueError,
    ) as error:

        raise ValidationError(
            "写真の保存に失敗しました。"
        ) from error

    if not image_url.startswith("https://"):
        raise ValidationError(
            "写真の保存先URLを取得できませんでした。"
        )

    return image_url
