
import html
import json
import os
import re
import time
from pathlib import Path

import requests

from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

from outings.models import TouristSpot


COMMONS_API = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = os.environ.get(
    "WIKIMEDIA_USER_AGENT",
    "YappTourismImageResearch/0.1 "
    "(https://yahan-app.onrender.com/)",
)


def clean_text(value):
    if isinstance(value, dict):
        value = value.get("value", "")

    return html.unescape(
        strip_tags(str(value or ""))
    ).strip()


def allowed_license(metadata):
    """
    Conservative initial license filter.

    Only CC0, Public Domain, CC BY,
    and CC BY-SA are considered candidates.
    """

    license_name = clean_text(
        metadata.get("LicenseShortName", {})
    )

    normalized = license_name.upper().strip()

    if normalized.startswith("CC0"):
        return True

    if normalized in ("PUBLIC DOMAIN", "PD"):
        return True

    if normalized.startswith("CC BY"):
        if "-NC" in normalized or "-ND" in normalized:
            return False
        return True

    return False


def search_commons(session, spot, per_spot):
    """
    Search Wikimedia Commons for original
    geographical or facility name.
    """

    query = spot.title_original.strip()

    if not query:
        return []

    response = session.get(
        COMMONS_API,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 15,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime",
            "iiurlwidth": 800,
            "format": "json",
            "formatversion": 2,
        },
        timeout=30,
    )

    response.raise_for_status()

    pages = response.json().get("query", {}).get("pages", [])

    return commons_candidates(pages, per_spot)


def commons_candidates(pages, per_spot):
    """
    Usable photos from a Commons API page list,
    with license, author and source.
    """

    candidates = []

    for page in pages:
        image_infos = page.get("imageinfo") or []

        if not image_infos:
            continue

        info = image_infos[0]

        if not info.get("mime", "").startswith("image/"):
            continue

        # Use still images, not SVG or animated GIF.
        if info.get("mime") not in (
            "image/jpeg",
            "image/png",
            "image/webp",
        ):
            continue

        metadata = info.get("extmetadata") or {}

        if not allowed_license(metadata):
            continue

        image_url = info.get("thumburl") or ""
        source_url = info.get("descriptionurl") or ""
        original_url = info.get("url") or ""

        if not (
            image_url.startswith("https://")
            and source_url.startswith("https://")
            and original_url.startswith("https://")
        ):
            continue

        license_name = clean_text(
            metadata.get("LicenseShortName")
        )

        license_url = clean_text(
            metadata.get("LicenseUrl")
        )

        author = clean_text(
            metadata.get("Artist")
        )

        description = clean_text(
            metadata.get("ImageDescription")
        )

        title = page.get("title", "")

        candidates.append({
            "file_title": title,
            "image_url": image_url,
            "original_url": original_url,
            "source_url": source_url,
            "license": license_name,
            "license_url": license_url,
            "author": author,
            "description": description[:400],
            "needs_review": True,
            "coordinates": (page.get("coordinates") or [None])[0],
            "width": info.get("width") or 0,
            "height": info.get("height") or 0,
        })

        if len(candidates) >= per_spot:
            break

    return candidates


def build_html_report(results):
    parts = [
        "<!doctype html>",
        '<html lang="ja">',
        '<meta charset="utf-8">',
        '<meta name="viewport" '
        'content="width=device-width, initial-scale=1">',
        "<title>Yapp 写真候補チェック</title>",
        "<style>",
        "body{font-family:sans-serif;max-width:1050px;"
        "margin:30px auto;padding:15px;background:#f7f9fb}",
        "h1{font-size:24px}",
        "section{background:#fff;padding:20px;"
        "border-radius:14px;margin:20px 0}",
        ".grid{display:grid;"
        "grid-template-columns:repeat(auto-fit,minmax(220px,1fr));"
        "gap:14px}",
        ".card{border:1px solid #ddd;"
        "border-radius:10px;overflow:hidden;padding:10px}",
        ".card img{width:100%;height:170px;"
        "object-fit:cover;background:#eee}",
        "small{display:block;line-height:1.7}",
        "a{color:#166a75}",
        "</style>",
        "<h1>Yapp 旅行写真の候補</h1>",
        "<p>写真・撮影場所・著作者・ライセンスを"
        "確認してから採用してください。</p>",
    ]

    for item in results:

        spot_title = html.escape(item["title"])

        parts.append("<section>")
        parts.append(
            f"<h2>{spot_title} "
            f"({item['score']}点)</h2>"
        )
        parts.append('<div class="grid">')

        if not item["candidates"]:
            parts.append(
                "<p>条件に合う候補が見つかりませんでした。</p>"
            )

        for candidate in item["candidates"]:

            def safe(value):
                return html.escape(
                    str(value or ""),
                    quote=True,
                )

            parts.append('<div class="card">')

            parts.append(
                '<img loading="lazy" src="'
                + safe(candidate["image_url"])
                + '" alt="">'
            )

            parts.append(
                "<p><strong>"
                + safe(candidate["file_title"])
                + "</strong></p>"
            )

            parts.append(
                "<small>撮影者："
                + safe(candidate["author"])
                + "</small>"
            )

            parts.append(
                "<small>ライセンス："
                + safe(candidate["license"])
                + "</small>"
            )

            parts.append(
                "<small>説明："
                + safe(candidate["description"][:180])
                + "</small>"
            )

            parts.append(
                '<p><a target="_blank" '
                'rel="noopener noreferrer" href="'
                + safe(candidate["source_url"])
                + '">Wikimedia Commonsで確認</a></p>'
            )

            parts.append("</div>")

        parts.append("</div></section>")

    parts.append("</html>")

    return "\n".join(parts)


class Command(BaseCommand):

    help = (
        "Find Wikimedia Commons photo candidates "
        "for high-rated tourism spots."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--limit",
            type=int,
            default=5,
        )

        parser.add_argument(
            "--per-spot",
            type=int,
            default=3,
        )

    def handle(self, *args, **options):

        limit = options["limit"]
        per_spot = options["per_spot"]

        if not 1 <= limit <= 50:
            raise ValueError(
                "--limit must be between 1 and 50"
            )

        if not 1 <= per_spot <= 5:
            raise ValueError(
                "--per-spot must be between 1 and 5"
            )

        spots = list(
            TouristSpot.objects.filter(
                status=TouristSpot.Status.PUBLISHED,
                ai_quality_score__isnull=False,
            )
            .order_by(
                "-ai_quality_score",
                "pk",
            )[:limit]
        )

        session = requests.Session()

        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

        results = []

        for index, spot in enumerate(spots, 1):

            self.stdout.write(
                f"[{index}/{len(spots)}] "
                f"{spot.title_original}"
            )

            candidates = []

            try:
                candidates = search_commons(
                    session,
                    spot,
                    per_spot,
                )

            except requests.RequestException as error:
                self.stderr.write(
                    f"  Search error: {error}"
                )

            self.stdout.write(
                f"  Found: {len(candidates)} candidates"
            )

            results.append({
                "spot_id": spot.pk,
                "title": spot.title_original,
                "score": spot.ai_quality_score,
                "candidates": candidates,
            })

            time.sleep(0.8)

        output_dir = Path("tourist_image_tests")
        output_dir.mkdir(exist_ok=True)

        json_path = (
            output_dir / "commons_candidates.json"
        )

        html_path = (
            output_dir / "commons_candidates.html"
        )

        json_path.write_text(
            json.dumps(
                results,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        html_path.write_text(
            build_html_report(results),
            encoding="utf-8",
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Photo candidate search completed."
            )
        )

        self.stdout.write(
            f"JSON: {json_path.resolve()}"
        )

        self.stdout.write(
            f"HTML: {html_path.resolve()}"
        )

        self.stdout.write(
            "No database records were modified."
        )
