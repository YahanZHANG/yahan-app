
"""
Switzerland Tourism OpenData API client.

Read-only API access.
Does not modify the Django database.
"""

import os
from urllib.parse import urlparse

import requests


BASE_URL = "https://opendata.myswitzerland.io/v1"

SUPPORTED_TYPES = (
    "attractions",
    "tours",
    "destinations",
    "offers",
)


class MySwitzerlandAPIError(Exception):
    pass


def fetch_spots(
    spot_type,
    pages=1,
    page_size=10,
    language="de",
):

    if spot_type not in SUPPORTED_TYPES:
        raise ValueError(
            f"Unsupported spot type: {spot_type}"
        )

    api_key = os.environ.get(
        "MYSWITZERLAND_API_KEY", ""
    ).strip()

    if not api_key:
        raise MySwitzerlandAPIError(
            "MYSWITZERLAND_API_KEY is not set."
        )

    if not 1 <= pages <= 1000:
        raise ValueError("pages must be 1-1000")

    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be 1-100")

    session = requests.Session()

    session.headers.update({
        "x-api-key": api_key,
        "Accept": "application/json",
        "User-Agent": "YappOutings/1.0",
    })

    all_items = []
    seen_ids = set()

    try:
        for page_number in range(pages):

            response = session.get(
                f"{BASE_URL}/{spot_type}/",
                params={
                    "lang": language,
                    "limit": page_size,
                    "page": page_number,
                    "expand": "true",
                    "striphtml": "true",
                },
                timeout=45,
            )

            try:
                response.raise_for_status()
                payload = response.json()
            except (
                requests.RequestException,
                ValueError,
            ) as exc:
                raise MySwitzerlandAPIError(
                    f"{spot_type}, page {page_number}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc

            if not isinstance(payload, dict):
                raise MySwitzerlandAPIError(
                    "Unexpected API response."
                )

            items = payload.get("data", [])

            if not isinstance(items, list):
                raise MySwitzerlandAPIError(
                    "API data is not a list."
                )

            if not items:
                break

            for item in items:

                if not isinstance(item, dict):
                    continue

                identifier = str(
                    item.get("identifier") or ""
                ).strip()

                if not identifier:
                    continue

                if identifier in seen_ids:
                    continue

                seen_ids.add(identifier)
                all_items.append(item)

            page_info = (
                payload.get("meta", {})
                .get("page", {})
            )

            total_pages = page_info.get(
                "totalPages"
            )

            if (
                isinstance(total_pages, int)
                and page_number + 1 >= total_pages
            ):
                break

    except requests.RequestException as exc:
        raise MySwitzerlandAPIError(
            f"API request failed: {exc}"
        ) from exc

    finally:
        session.close()

    return all_items


def extract_classifications(item):

    result = {}

    for classification in item.get(
        "classification", []
    ):

        if not isinstance(classification, dict):
            continue

        name = classification.get("name")

        if not name:
            continue

        values = classification.get(
            "values", []
        )

        if not isinstance(values, list):
            continue

        result[name] = [
            {
                "name": value.get("name", ""),
                "title": value.get("title", ""),
            }
            for value in values
            if isinstance(value, dict)
        ]

    return result


def extract_images(item):

    images = item.get("image", [])

    if not isinstance(images, list):
        return []

    return [
        {
            "url": image.get("url", ""),
            "name": image.get("name", ""),
            "copyrightHolder": image.get(
                "copyrightHolder", ""
            ),
            "publisher": image.get(
                "publisher", ""
            ),
        }
        for image in images
        if isinstance(image, dict)
    ]


def extract_details(item, spot_type):

    details = {}

    if spot_type == "tours":
        details["specs"] = item.get(
            "specs", {}
        )

        details["switzerlandMobility"] = (
            item.get("switzerlandMobility", {})
        )

        details["itinerary"] = item.get(
            "itinerary", []
        )

    elif spot_type == "destinations":
        details["category"] = item.get(
            "category", ""
        )

    elif spot_type == "attractions":
        details["isAccessibleForFree"] = (
            item.get("isAccessibleForFree")
        )

        details["recommendedSeason"] = (
            item.get("recommendedSeason")
        )

        details["price"] = item.get(
            "price"
        )

    elif spot_type == "offers":
        details["priceSpecification"] = (
            item.get("priceSpecification", {})
        )

        details["validFrom"] = item.get(
            "validFrom"
        )

        details["validThrough"] = item.get(
            "validThrough"
        )

    return details


def normalize_spot(item, spot_type):

    identifier = str(
        item.get("identifier") or ""
    ).strip()

    title = str(
        item.get("name") or ""
    ).strip()

    url = str(
        item.get("url") or ""
    ).strip()

    parsed = urlparse(url)

    if not (
        identifier
        and title
        and parsed.scheme == "https"
        and parsed.hostname in (
            "www.myswitzerland.com",
            "myswitzerland.com",
        )
    ):
        return None

    geo = item.get("geo") or {}

    if not isinstance(geo, dict):
        geo = {}

    subject = item.get("subjectOf") or {}

    if not isinstance(subject, dict):
        subject = {}

    return {
        "external_id": identifier,
        "spot_type": spot_type,
        "title_original": title[:300],
        "summary_original": str(
            item.get("abstract") or ""
        ),
        "description_original": str(
            item.get("description") or ""
        ),
        "official_url": url,
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "classifications": (
            extract_classifications(item)
        ),
        "details": extract_details(
            item, spot_type
        ),
        "image_metadata": extract_images(item),
        "source_license": str(
            subject.get("license") or ""
        )[:300],
        "raw_data": item,
    }
