"""
写真の保存。おでかけと同じ Cloudinary (無料枠) に、小さな WebP にしてから送る。
食材の写真は Wikimedia Commons からも探せる (出典とライセンスを一緒に保存)。
"""

import logging
import re

from html import unescape
from urllib.parse import urlparse

import requests

from django.core.exceptions import ValidationError

from outings.management.commands.cleanup_outings import delete_photos
from outings.services.user_event_cloudinary import upload_user_event_photo
from outings.services.user_event_images import process_user_event_image


logger = logging.getLogger(__name__)

# 携帯の画面で十分な大きさ。1枚 100KB 前後になる
PHOTO_MAX_SIZE = 1200
PHOTO_QUALITY = 78

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_HEADERS = {"User-Agent": "YappWashoku/1.0 (https://yahan-app.onrender.com/washoku/)"}


def upload_photo(uploaded_file, folder):
    """
    写真を小さくして保存し、URL を返す。読めない・送れないときは ValidationError。
    """

    processed = process_user_event_image(
        uploaded_file,
        max_size=PHOTO_MAX_SIZE,
        quality=PHOTO_QUALITY,
    )

    return upload_user_event_photo(
        processed,
        folder=f"yapp/washoku/{folder}",
        filename="photo.webp",
    )


def delete_uploaded_photos(*urls):
    """
    Cloudinary に保存した写真を消す (Wikimedia など、ほかの URL は何もしない)。
    """

    urls = [url for url in urls if url]

    if urls:
        delete_photos(urls, logger.warning)


def thumbnail_url(url, size):
    """
    Cloudinary の写真なら、正方形に切り抜いた小さい版の URL にする。
    """

    parsed = urlparse(url or "")

    if parsed.hostname != "res.cloudinary.com" or "/image/upload/" not in parsed.path:
        return url

    return url.replace("/image/upload/", f"/image/upload/c_fill,w_{size},h_{size}/", 1)


# スイス側の代わりの食材は、写真がよく見つかる言葉 (英語名や学名) で探す
COMMONS_QUERIES = {
    "豚薄切り肉": "sliced pork meat raw",
    "豚バラ肉": "raw pork belly",
    "牛薄切り肉": "thinly sliced beef raw",
    "白身魚": "cod fillet raw",
    "おでん種": "fish balls",
    "ピザ用チーズ": "grated mozzarella cheese",
    "米": "japonica rice grains",
    "サンドイッチ用パン": "sliced toast bread",
    "リーキ": "leeks vegetable",
    "スプリングオニオン": "spring onions bunch",
    "大根（Rettich）": "white radish Rettich",
    "パースニップ": "parsnips vegetable",
    "マッシュルーム": "button mushrooms Agaricus bisporus",
    "バジル": "basil leaves Ocimum basilicum",
    "コールラビ": "kohlrabi vegetable",
    "白かぶ": "white turnips Brassica rapa",
    "ラディッシュ": "radishes bunch",
    "スイスチャード": "Swiss chard Mangold",
    "チンゲン菜": "bok choy vegetable",
    "とんがりキャベツ": "pointed cabbage Spitzkohl",
    "ちりめんキャベツ": "savoy cabbage",
    "黒ごぼう": "black salsify Scorzonera hispanica",
    "絹さや": "snow peas pods",
    "いんげん": "green beans Phaseolus vulgaris pods",
    "パドロン": "Padrón peppers",
    "クレス": "garden cress Lepidium sativum",
    "ベアラウフ": "Allium ursinum leaves",
    "さつまいも": "sweet potatoes tubers",
    "エリンギ": "Pleurotus eryngii mushrooms",
    "ひらたけ": "oyster mushrooms Pleurotus ostreatus",
    "こんにゃく": "shirataki noodles",
    "日本酒": "sake bottle",
    "鶏がらスープの素": "chicken bouillon cubes",
    "コンソメ": "vegetable bouillon powder",
    "ウスターソース": "Worcestershire sauce bottle",
    "バニラシュガー": "vanilla sugar",
}


def commons_query(ingredient):
    """
    Wikimedia Commons で探す言葉。決めてある言葉がなければ、ドイツ語名の最初の候補 (例: "Weisse Rüben / Mairübli" → "Weisse Rüben")。
    """

    if ingredient.name in COMMONS_QUERIES:
        return COMMONS_QUERIES[ingredient.name]

    name = ingredient.name_de or ingredient.name
    name = name.split("/")[0]
    name = re.sub(r"\(.*?\)", "", name)
    name = name.split(",")[0]

    return name.strip()


def plain_text(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html or ""))).strip()


def find_commons_photo(query):
    """
    Commons で写真を1枚探す。見つかれば {url, credit, source}、なければ None。
    """

    response = requests.get(
        COMMONS_API,
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": 6,
            "gsrlimit": 8,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 640,
        },
        headers=COMMONS_HEADERS,
        timeout=15,
    )

    response.raise_for_status()

    pages = sorted(
        response.json().get("query", {}).get("pages", {}).values(),
        key=lambda page: page.get("index", 0),
    )

    for page in pages:

        info = (page.get("imageinfo") or [{}])[0]

        if info.get("mime") not in ("image/jpeg", "image/png") or info.get("width", 0) < 400:
            continue

        meta = info.get("extmetadata", {})
        artist = plain_text(meta.get("Artist", {}).get("value"))
        license_name = plain_text(meta.get("LicenseShortName", {}).get("value"))

        credit = " / ".join(part for part in (artist, license_name, "Wikimedia Commons") if part)

        return {
            "url": info.get("thumburl") or info.get("url"),
            "credit": credit[:300],
            "source": info.get("descriptionurl", ""),
        }

    return None
