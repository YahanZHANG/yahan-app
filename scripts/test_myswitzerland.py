
"""
Switzerland Tourism OpenData API test.

Fetch small samples from four official API endpoints.
No Django database changes.
No API key is printed or saved.

Usage:
    python scripts/test_myswitzerland.py
"""

import json
import os
from pathlib import Path

import requests


BASE_URL = "https://opendata.myswitzerland.io/v1"

API_KEY = os.environ.get(
    "MYSWITZERLAND_API_KEY", ""
).strip()

ENDPOINTS = [
    "attractions",
    "tours",
    "destinations",
    "offers",
]

OUTPUT_DIR = Path("local_data") / "myswitzerland"


def fetch_endpoint(session, endpoint):
    url = f"{BASE_URL}/{endpoint}/"

    response = session.get(
        url,
        params={
            "lang": "de",
            "limit": 5,
            "expand": "true",
            "striphtml": "true",
        },
        timeout=45,
    )

    response.raise_for_status()

    return response.json()


def show_preview(endpoint, payload):
    print()
    print("=" * 65)
    print(f"ENDPOINT: {endpoint}")
    print("=" * 65)

    if not isinstance(payload, dict):
        print("Unexpected response type:", type(payload).__name__)
        return

    print("Top-level keys:", list(payload.keys()))

    meta = payload.get("meta", {})

    if isinstance(meta, dict):
        print(
            "Paging:",
            json.dumps(
                meta.get("paging", {}),
                ensure_ascii=False,
                default=str,
            )[:800],
        )

    data = payload.get("data", [])

    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        print("Unexpected data type:", type(data).__name__)
        return

    print("Number of items:", len(items))

    for index, item in enumerate(items[:3], start=1):
        if not isinstance(item, dict):
            continue

        print()
        print(f"--- Item {index} ---")

        for field in (
            "identifier",
            "id",
            "name",
            "url",
            "abstract",
            "description",
            "geo",
            "classification",
        ):
            if field not in item:
                continue

            value = item[field]

            if isinstance(value, (dict, list)):
                value = json.dumps(
                    value,
                    ensure_ascii=False,
                    default=str,
                )

            print(f"{field}: {str(value)[:350]}")

        print("Available fields:", list(item.keys()))


def main():
    if not API_KEY:
        raise SystemExit(
            "MYSWITZERLAND_API_KEY is not set."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    session = requests.Session()

    session.headers.update({
        "x-api-key": API_KEY,
        "Accept": "application/json",
        "User-Agent": "YappOutings/1.0",
    })

    success = 0

    for endpoint in ENDPOINTS:
        print()
        print(f"Fetching {endpoint}...")

        try:
            payload = fetch_endpoint(
                session,
                endpoint,
            )

        except requests.HTTPError as exc:
            status = (
                exc.response.status_code
                if exc.response is not None
                else "unknown"
            )

            print(
                f"HTTP error for {endpoint}: {status}"
            )
            continue

        except (requests.RequestException, ValueError) as exc:
            print(
                f"Fetch error for {endpoint}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        show_preview(
            endpoint,
            payload,
        )

        output_path = (
            OUTPUT_DIR / f"{endpoint}_sample.json"
        )

        output_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print()
        print("Saved:", output_path)

        success += 1

    print()
    print("=" * 65)
    print(
        f"COMPLETE: {success}/{len(ENDPOINTS)} "
        "endpoints succeeded"
    )


if __name__ == "__main__":
    main()
