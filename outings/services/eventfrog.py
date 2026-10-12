
"""Read Eventfrog Public API into normalized event candidates.

This module does not write Django database records.
It collects events, resolves supported Swiss cantons, and groups occurrences.
"""

import json
import os
import time
import unicodedata

from datetime import timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from django.utils.dateparse import parse_datetime


# =========================================================
# API configuration
# =========================================================

API_URL = "https://api.eventfrog.net/public/v1/events"
LOCATION_URL = "https://api.eventfrog.net/public/v1/locations"

TZ = ZoneInfo("Europe/Zurich")

REGIONS = {"ZH", "AG", "BE", "BS", "BL", "LU", "ZG"}

REGION_NAMES = {
    "ZÜRICH": "ZH",
    "ZURICH": "ZH",
    "AARGAU": "AG",
    "BERN": "BE",
    "BASEL-STADT": "BS",
    "BASEL-LANDSCHAFT": "BL",
    "LUZERN": "LU",
    "LUCERNE": "LU",
    "ZUG": "ZG",
}


# =========================================================
# Known municipality-to-canton mapping
# =========================================================

CITY_TO_REGION = {
    "ZÜRICH": "ZH",
    "ZURICH": "ZH",
    "ZUERICH": "ZH",
    "WINTERTHUR": "ZH",
    "USTER": "ZH",
    "DIETIKON": "ZH",
    "DÜBENDORF": "ZH",
    "DUEBENDORF": "ZH",
    "BÜLACH": "ZH",
    "BUELACH": "ZH",
    "HORGEN": "ZH",
    "WÄDENSWIL": "ZH",
    "WAEDENSWIL": "ZH",
    "KLOTEN": "ZH",
    "SCHLIEREN": "ZH",
    "OPFIKON": "ZH",
    "WETZIKON": "ZH",
    "MEILEN": "ZH",

    "BASSEL": "BS",
    "BASEL": "BS",
    "RIEHEN": "BS",
    "BETTINGEN": "BS",

    "LIESTAL": "BL",
    "MUTTENZ": "BL",
    "PRATTELN": "BL",
    "ALLSCHWIL": "BL",
    "BIRSFELDEN": "BL",
    "REINACH BL": "BL",

    "AARAU": "AG",
    "BADEN": "AG",
    "WETTINGEN": "AG",
    "LENZBURG": "AG",
    "ZOFINGEN": "AG",
    "SPREITENBACH": "AG",
    "RHEINFELDEN": "AG",
    "BRUGG": "AG",
    "WOHLEN AG": "AG",

    "BERN": "BE",
    "BERNE": "BE",
    "THUN": "BE",
    "BIEL": "BE",
    "BIENNE": "BE",
    "BIEL/BIENNE": "BE",
    "BURGDORF": "BE",
    "INTERLAKEN": "BE",
    "SPIEZ": "BE",

    "LUZERN": "LU",
    "LUCERNE": "LU",
    "KRIENS": "LU",
    "EMMEN": "LU",
    "SURSEE": "LU",
    "HORW": "LU",

    "ZUG": "ZG",
    "BAAR": "ZG",
    "CHAM": "ZG",
    "STEINHAUSEN": "ZG",
    "ROTKREUZ": "ZG",
    "HÜNENBERG": "ZG",
}


# =========================================================
# Helpers
# =========================================================

def translated(value):
    """Choose a usable translation from Eventfrog fields."""
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for lang in ("de", "en", "fr", "it", "ja"):
            text = value.get(lang)
            if isinstance(text, str) and text.strip():
                return text.strip()

        for text in value.values():
            if isinstance(text, str) and text.strip():
                return text.strip()

    return ""


def dt(value):
    """Return an aware datetime, or None."""
    parsed = parse_datetime(str(value or ""))

    if parsed and timezone.is_aware(parsed):
        return parsed

    return None


def is_true(value):
    return value is True or str(value).lower() == "true"


def find_in(obj, *keys):
    """Read the first nonempty key, supporting dotted paths."""
    for key in keys:
        value = obj

        for part in key.split("."):
            value = (
                value.get(part)
                if isinstance(value, dict)
                else None
            )

        if value not in (None, "", [], {}):
            return value

    return None


def location_ids(event):
    values = event.get("locationIds") or []

    if isinstance(values, str):
        try:
            values = json.loads(values)
        except ValueError:
            values = []

    if not isinstance(values, list):
        return []

    return [str(value) for value in values]


def safe_https_url(value):
    """Accept only absolute HTTPS URLs with a hostname."""
    if not isinstance(value, str):
        return ""

    value = value.strip()

    if len(value) > 1000:
        return ""

    try:
        parsed = urlparse(value)
    except ValueError:
        return ""

    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return ""

    return value


# =========================================================
# Event images
# =========================================================

def extract_image(event):
    """Extract Eventfrog emblem URL and image credit.

    The API commonly returns:
        emblemToShow: {
            "url": "...",
            "width": 800,
            "height": 600
        }

    Historical/string variants are also supported.

    This does NOT download or grant rights to reuse the image.
    """
    emblem = event.get("emblemToShow")

    image_url = ""

    if isinstance(emblem, dict):
        image_url = (
            emblem.get("url")
            or emblem.get("imageUrl")
            or ""
        )

    elif isinstance(emblem, str):
        image_url = emblem

    image_url = safe_https_url(image_url)

    credit = translated(event.get("emblemCredits"))

    return image_url, credit[:500]


# =========================================================
# Collect events
# =========================================================

def collect(
    *,
    pages=40,
    per_page=1000,
    days=45,
    raw_events=None,
):
    now = timezone.now()
    horizon = now + timedelta(days=days)

    if raw_events is not None:
        records = raw_events

    else:
        token = os.environ.get(
            "EVENTFROG_API_TOKEN", ""
        ).strip()

        if not token:
            raise ValueError(
                "EVENTFROG_API_TOKEN がありません"
            )

        records = []

        with requests.Session() as session:
            session.headers.update({
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            })

            for page in range(1, pages + 1):
                response = session.get(
                    API_URL,
                    params={
                        "country": "CH",
                        "from": now.astimezone(TZ).isoformat(),
                        "to": horizon.astimezone(TZ).isoformat(),
                        "page": page,
                        "perPage": per_page,
                    },
                    timeout=40,
                )

                response.raise_for_status()
                payload = response.json()

                if (
                    not isinstance(payload, dict)
                    or not isinstance(
                        payload.get("events"), list
                    )
                ):
                    raise ValueError(
                        f"Eventfrog response shape unexpected "
                        f"on page {page}"
                    )

                part = payload["events"]
                records.extend(part)

                print(
                    f"[Eventfrog] Events page "
                    f"{page}/{pages}: "
                    f"{len(part)} rows; "
                    f"total={len(records)}",
                    flush=True,
                )

                if len(part) < per_page or not part:
                    break

                time.sleep(1.2)

    # =====================================================
    # Normalize events
    # =====================================================

    result = {}
    cancelled = set()

    for item in records:
        if not isinstance(item, dict):
            continue

        ext_id = str(item.get("id") or "").strip()

        start = dt(item.get("begin"))
        end = dt(item.get("end"))

        if (
            not ext_id
            or not start
            or not end
            or end <= start
            or not now <= start <= horizon
        ):
            continue

        if is_true(item.get("cancelled")):
            cancelled.add(ext_id)
            continue

        if (
            item.get("published") is not True
            or item.get("visible") is not True
        ):
            continue

        title = translated(item.get("title"))
        url = safe_https_url(
            str(item.get("url") or "")
        )

        if not title or not url:
            continue

        host = (urlparse(url).hostname or "").lower()

        if host not in (
            "eventfrog.ch",
            "www.eventfrog.ch",
        ):
            continue

        raw_description = (
            translated(item.get("descriptionAsHTML"))
            or translated(item.get("shortDescription"))
        )

        description = BeautifulSoup(
            raw_description,
            "html.parser",
        ).get_text(" ", strip=True)[:1800]

        image_url, image_credit = extract_image(item)

        result[ext_id] = {
            "id": ext_id,
            "group_id": str(
                item.get("groupId") or ""
            ),
            "title": title[:250],
            "description": description,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "url": url,
            "location_ids": location_ids(item),
            "organizer": translated(
                item.get("organizerName")
            ),
            "image_url": image_url,
            "image_credit": image_credit,
        }

    for ext_id in cancelled:
        result.pop(ext_id, None)

    print(
        "[Eventfrog] Normalized events="
        f"{len(result)}; "
        "with image URLs="
        f"{sum(bool(e['image_url']) for e in result.values())}",
        flush=True,
    )

    return list(result.values())


# =========================================================
# Enrich locations
# =========================================================

def enrich_locations(
    events,
    *,
    offline=False,
    cache_file=None,
):
    """Resolve locations with incremental disk caching."""
    cache = {}

    if cache_file and cache_file.exists():
        data = json.loads(
            cache_file.read_text(encoding="utf-8")
        )

        if not isinstance(data, dict):
            raise ValueError(
                "Location cache must be a JSON object"
            )

        cache = data

    ids = sorted({
        location_id
        for event in events
        for location_id in event["location_ids"]
    })

    missing = [
        location_id
        for location_id in ids
        if location_id not in cache
    ]

    print(
        f"[Eventfrog] Locations required={len(ids)} "
        f"cached={len(ids) - len(missing)} "
        f"missing={len(missing)}",
        flush=True,
    )

    if missing and not offline:
        token = os.environ.get(
            "EVENTFROG_API_TOKEN", ""
        ).strip()

        if not token:
            raise ValueError(
                "EVENTFROG_API_TOKEN がありません"
            )

        if cache_file:
            cache_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        with requests.Session() as session:
            session.headers.update({
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            })

            chunk_size = 40

            for idx in range(
                0,
                len(missing),
                chunk_size,
            ):
                chunk = missing[
                    idx:idx + chunk_size
                ]

                for attempt in range(4):
                    try:
                        response = session.get(
                            LOCATION_URL,
                            params=[
                                ("id", value)
                                for value in chunk
                            ],
                            timeout=40,
                        )

                        if response.status_code in (
                            429, 500, 502, 503, 504
                        ):
                            if attempt == 3:
                                response.raise_for_status()

                            retry_after = response.headers.get(
                                "Retry-After", ""
                            ).strip()

                            try:
                                wait = min(
                                    180.0,
                                    max(
                                        1.0,
                                        float(retry_after),
                                    ),
                                )
                            except ValueError:
                                wait = min(
                                    120.0,
                                    15.0 * (2 ** attempt),
                                )

                            print(
                                f"[Eventfrog] HTTP "
                                f"{response.status_code}, "
                                f"waiting {wait:g}s "
                                f"before retry "
                                f"({attempt + 1}/4)",
                                flush=True,
                            )

                            time.sleep(wait)
                            continue

                        response.raise_for_status()
                        payload = response.json()

                        if isinstance(payload, list):
                            part = payload

                        elif isinstance(payload, dict):
                            part = (
                                payload.get("locations")
                                or payload.get("items")
                                or payload.get("data")
                                or []
                            )
                        else:
                            part = []

                        if isinstance(part, dict):
                            part = (
                                part.get("locations")
                                or part.get("items")
                                or []
                            )

                        if not isinstance(part, list):
                            raise ValueError(
                                "Location API response "
                                "shape unexpected"
                            )

                        for item in part:
                            if (
                                isinstance(item, dict)
                                and item.get("id") is not None
                            ):
                                cache[str(item["id"])] = item

                        if cache_file:
                            tmp = cache_file.with_name(
                                cache_file.name + ".tmp"
                            )

                            tmp.write_text(
                                json.dumps(
                                    cache,
                                    ensure_ascii=False,
                                ),
                                encoding="utf-8",
                            )

                            tmp.replace(cache_file)

                        print(
                            "[Eventfrog] Locations progress "
                            f"{min(idx + len(chunk), len(missing))}"
                            f"/{len(missing)}; "
                            f"cache={len(cache)}",
                            flush=True,
                        )
                        break

                    except (
                        requests.Timeout,
                        requests.ConnectionError,
                    ) as exc:
                        if attempt == 3:
                            raise

                        wait = min(
                            60,
                            5 * (2 ** attempt),
                        )

                        print(
                            "[Eventfrog] Network error, "
                            f"retry in {wait}s: "
                            f"{type(exc).__name__}",
                            flush=True,
                        )

                        time.sleep(wait)

                time.sleep(3.0)

    # =====================================================
    # Map event locations to cantons
    # =====================================================

    output = []

    for event in events:
        info = [
            cache[location_id]
            for location_id in event["location_ids"]
            if (
                location_id in cache
                and isinstance(cache[location_id], dict)
            )
        ]

        resolved = []

        for loc in info:
            raw = translated(
                find_in(
                    loc,
                    "canton",
                    "cantonCode",
                    "state",
                    "region",
                    "address.canton",
                    "address.state",
                )
            ).upper().strip()

            city = translated(
                find_in(
                    loc,
                    "city",
                    "cityName",
                    "town",
                    "municipality",
                    "address.city",
                )
            ).strip()

            region = (
                raw
                if raw in REGIONS
                else REGION_NAMES.get(raw, "")
            )

            if not region:
                region = CITY_TO_REGION.get(
                    city.upper(), ""
                )

            venue = translated(
                find_in(
                    loc,
                    "name",
                    "title",
                    "locationName",
                )
            ).strip()

            if region and city and venue:
                resolved.append(
                    (region, city, venue)
                )

        # Do not guess ambiguous or unknown cantons.
        if (
            not resolved
            or len({row[0] for row in resolved}) != 1
        ):
            continue

        region, city, venue = resolved[0]

        output.append({
            **event,
            "region": region,
            "city": city,
            "venue": venue,
        })

    return output


# =========================================================
# Group repeated performances
# =========================================================

def group(events):
    """Group matching programs and retain their occurrences."""

    def key(value):
        return " ".join(
            unicodedata.normalize(
                "NFKC", str(value or "")
            ).casefold().split()
        )

    grouped = {}

    for event in events:
        group_key = (
            key(event["title"]),
            event["region"],
            key(event["venue"]),
            key(event["organizer"]),
        )

        if group_key not in grouped:
            grouped[group_key] = {
                **event,
                "occurrences": [],
            }

        current = grouped[group_key]

        current["occurrences"].append({
            "id": event["id"],
            "start": event["start"],
            "end": event["end"],
        })

        # Use a valid image from another performance
        # if the first one has no image.
        if (
            not current.get("image_url")
            and event.get("image_url")
        ):
            current["image_url"] = event["image_url"]
            current["image_credit"] = event.get(
                "image_credit", ""
            )

    for event in grouped.values():
        event["occurrences"].sort(
            key=lambda item: item["start"]
        )

        event["start"] = (
            event["occurrences"][0]["start"]
        )

    return sorted(
        grouped.values(),
        key=lambda item: item["start"],
    )
