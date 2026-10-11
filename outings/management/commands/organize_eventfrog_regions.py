"""Django management command: locations lookup and series aggregation (no DB writes)."""
import csv
import json
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

API = "https://api.eventfrog.net/public/v1/locations"
OUT = Path("outings_audit")
INPUT_FILES = sorted(
    OUT.glob("eventfrog_future_events*.csv")
)
CANTON_NAMES = {
    "ZH": "Zürich", "BS": "Basel-Stadt", "BL": "Basel-Landschaft",
    "ZG": "Zug", "LU": "Luzern", "AG": "Aargau", "BE": "Bern",
}
CITY_TO_REGION = {
    # Zürich
    "zürich": "ZH",
    "zurich": "ZH",
    "zuerich": "ZH",
    "winterthur": "ZH",
    "urdorf": "ZH",
    "affoltern am albis": "ZH",
    "bülach": "ZH",
    "buelach": "ZH",
    "dietikon": "ZH",
    "uster": "ZH",
    "dübendorf": "ZH",
    "duebendorf": "ZH",
    "horgen": "ZH",
    "wädenswil": "ZH",

    # Basel-Stadt
    "basel": "BS",
    "riehen": "BS",
    "bettingen": "BS",

    # Basel-Landschaft
    "liestal": "BL",
    "muttenz": "BL",
    "pratteln": "BL",
    "reinach bl": "BL",
    "allschwil": "BL",
    "birsfelden": "BL",

    # Aargau
    "aarau": "AG",
    "baden": "AG",
    "wettingen": "AG",
    "lenzburg": "AG",
    "zofingen": "AG",
    "safenwil": "AG",
    "spreitenbach": "AG",
    "magden": "AG",
    "rheinfelden": "AG",

    # Bern
    "bern": "BE",
    "berne": "BE",
    "thun": "BE",
    "biel": "BE",
    "bienne": "BE",
    "burgdorf": "BE",
    "interlaken": "BE",

    # Luzern
    "luzern": "LU",
    "lucerne": "LU",
    "sursee": "LU",
    "emmen": "LU",
    "kriens": "LU",
    "horw": "LU",

    # Zug
    "zug": "ZG",
    "cham": "ZG",
    "baar": "ZG",
    "steinhausen": "ZG",
    "rotkreuz": "ZG",
    "hünenberg": "ZG",
}
CANTON_ALIASES = {
    "zurich": "ZH", "zuerich": "ZH", "zürich": "ZH",
    "basel-stadt": "BS", "baselstadt": "BS", "basel-landschaft": "BL",
    "baselland": "BL", "zug": "ZG", "luzern": "LU", "lucerne": "LU",
    "aargau": "AG", "bern": "BE", "berne": "BE",
}
FIELDS = [
    "region", "city", "venue", "title", "first_begin", "last_end",
    "occurrence_count", "occurrence_starts", "score", "priority",
    "matched_topics", "series_key", "event_ids", "location_ids",
    "event_url", "description", "region_basis",
]


def localized(v):
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        for lang in ("de", "en", "fr", "it"):
            if isinstance(v.get(lang), str) and v[lang].strip():
                return v[lang].strip()
        return next((s.strip() for s in v.values() if isinstance(s, str) and s.strip()), "")
    return ""


def clean(v):
    v = unicodedata.normalize("NFKC", str(v or ""))
    return re.sub(r"\s+", " ", v).strip().casefold()


def get_nested(d, *paths):
    for path in paths:
        value = d
        for part in path.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(part)
        if value not in (None, "", [], {}):
            return value
    return None


def parse_ids(value):
    if isinstance(value, list):
        return [str(x) for x in value if x is not None]
    try:
        decoded = json.loads(value or "[]")
        return [str(x) for x in decoded] if isinstance(decoded, list) else []
    except (ValueError, TypeError):
        return []


def parse_date(text):
    d = parse_datetime(text or "")
    if d is None or timezone.is_naive(d):
        return None
    return d


def normalize_region(value):
    s = clean(localized(value))
    if s.upper() in CANTON_NAMES:
        return s.upper()
    return CANTON_ALIASES.get(s, "")


def extract_location(loc):
    """Conservative parsing: only actual fields; no city inferred from URL."""
    address = loc.get("address") if isinstance(loc.get("address"), dict) else {}
    city = localized(get_nested(loc, "city", "cityName", "town", "municipality", "address.city", "address.town"))
    canton = normalize_region(get_nested(loc, "canton", "cantonCode", "state", "region", "address.canton", "address.state"))
    venue = localized(get_nested(loc, "name", "title", "locationName"))
    if not city and clean(venue) == "landesmuseum zürich":
        city = "Zürich"
    if not canton and clean(city) in CITY_TO_REGION:
        canton = CITY_TO_REGION[clean(city)]
        basis = "known_city"
    elif canton:
        basis = "canton_field"
    else:
        basis = "unknown"
    return {"region": canton, "city": city, "venue": venue, "basis": basis,
            "raw_fields": sorted(loc.keys())}


def fetch_locations(ids, token, stdout):
    found = {}
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        for offset in range(0, len(ids), 100):
            chunk = ids[offset:offset + 100]
            # Repeated `id` is documented by Eventfrog API.
            params = [("id", ident) for ident in chunk]
            for attempt in range(3):
                try:
                    r = session.get(API, params=params, timeout=35)
                    if r.status_code in (429, 502, 503, 504) and attempt < 2:
                        time.sleep(3 * (attempt + 1))
                        continue
                    r.raise_for_status()
                    payload = r.json()
                    break
                except (requests.RequestException, ValueError) as exc:
                    raise CommandError(f"会場API取得失敗 ({offset}件目): {exc}") from exc
            if isinstance(payload, list):
                batch = payload
            elif isinstance(payload, dict):
                batch = payload.get("locations") or payload.get("items") or payload.get("data") or []
            else:
                batch = []
            if isinstance(batch, dict):
                batch = batch.get("locations") or batch.get("items") or []
            if not isinstance(batch, list):
                raise CommandError("会場API形式が不明です。レスポンス構造を確認してください")
            for loc in batch:
                if isinstance(loc, dict) and loc.get("id") is not None:
                    found[str(loc["id"])] = loc
            stdout.write(f"会場照会: {min(offset + 100, len(ids))}/{len(ids)} ID、照合 {len(found)}")
            time.sleep(2.1)
    finally:
        session.close()
    return found


class Command(BaseCommand):
    help = "Resolve Eventfrog locations and group repeats into review CSVs; no DB writes"

    def add_arguments(self, parser):
        parser.add_argument("--offline", action="store_true", help="既存会場キャッシュのみ使用")

    def handle(self, *args, **options):
        files = [p for p in INPUT_FILES if p.exists()]
        if not files:
            raise CommandError("対象CSVがありません。eventfrog_future_events*.csv を確認してください")
        rows_by_id = {}
        for path in files:
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    if row.get("id"):
                        rows_by_id[row["id"]] = row
        ids = sorted({lid for r in rows_by_id.values() for lid in parse_ids(r.get("location_ids"))})
        OUT.mkdir(exist_ok=True, parents=True)
        cache_path = OUT / "eventfrog_locations_cache.json"
        if cache_path.exists():
            with cache_path.open(encoding="utf-8") as f:
                cached = json.load(f)
        else:
            cached = {}
        if not isinstance(cached, dict):
            cached = {}
        missing = sorted(set(ids) - set(cached))
        if missing and not options["offline"]:
            token = os.environ.get("EVENTFROG_API_TOKEN", "").strip()
            if not token:
                raise CommandError("会場取得にはEVENTFROG_API_TOKENが必要です")
            cached.update(fetch_locations(missing, token, self.stdout))
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(cached, f, ensure_ascii=False, indent=2)
        now = timezone.now()
        groups = defaultdict(list)
        rejected = Counter()
        for row in rows_by_id.values():
            start = parse_date(row.get("begin"))
            end = parse_date(row.get("end"))
            if not start or not end or end <= now or end <= start:
                rejected["date_invalid_or_ended"] += 1
                continue
            if row.get("cancelled", "").lower() == "true" or row.get("visible", "").lower() == "false":
                rejected["not_publishable"] += 1
                continue
            location_ids = parse_ids(row.get("location_ids"))
            resolved = [extract_location(cached[lid]) for lid in location_ids if lid in cached]
            regions = sorted({v["region"] for v in resolved if v["region"]})
            # Ambiguous multi-canton events are not placed in one region.
            region = regions[0] if len(regions) == 1 else "UNKNOWN"
            venue = next((v["venue"] for v in resolved if v["venue"]), "")
            city = next((v["city"] for v in resolved if v["city"]), "")
            basis = next((v["basis"] for v in resolved if v["region"] == region), "unknown")
            # groupId is diagnostic only. Different groupIds can describe the same exhibition.
            # Include organizer and venue to prevent collapsing different events with same title.
            loc_identity = ",".join(sorted(location_ids)) if location_ids else f"unlocated:{row['id']}"
            key = (clean(row.get("title")), loc_identity, clean(row.get("organizer")))
            groups[key].append((row, start, end, region, city, venue, basis))

        output = []
        for key, items in groups.items():
            items.sort(key=lambda item: item[1])
            first = items[0]
            representative = first[0]
            starts = sorted({item[1].isoformat() for item in items})
            # Events of same name at same venue can still differ. Label as provisional series.
            output.append({
                "region": first[3], "city": first[4], "venue": first[5],
                "title": representative.get("title", ""),
                "first_begin": first[1].isoformat(),
                "last_end": max(item[2] for item in items).isoformat(),
                "occurrence_count": len(starts),
                "occurrence_starts": " | ".join(starts),
                "score": max(int(item[0].get("score") or 0) for item in items),
                "priority": "HIGH" if any(item[0].get("priority") == "HIGH" for item in items) else (
                    "MEDIUM" if any(item[0].get("priority") == "MEDIUM" for item in items) else "LOW"),
                "matched_topics": representative.get("matched_topics", ""),
                "series_key": " | ".join(key),
                "event_ids": " | ".join(item[0]["id"] for item in items),
                "location_ids": representative.get("location_ids", ""),
                "event_url": representative.get("url", ""),
                "description": representative.get("description", "")[:700],
                "region_basis": first[6],
            })

        output.sort(key=lambda r: (r["region"] == "UNKNOWN", -r["score"], r["first_begin"]))
        all_path = OUT / "eventfrog_grouped_by_region.csv"
        for path, part in [
            (all_path, output),
            (OUT / "eventfrog_grouped_priority.csv", [r for r in output if r["priority"] != "LOW" and r["region"] != "UNKNOWN"]),
            (OUT / "eventfrog_grouped_unknown.csv", [r for r in output if r["region"] == "UNKNOWN"]),
        ]:
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(part)
        diagnostics = {k: extract_location(v) for k, v in cached.items() if isinstance(v, dict)}
        with (OUT / "eventfrog_location_diagnostics.json").open("w", encoding="utf-8") as f:
            json.dump({"counts": dict(Counter(x["region"] for x in output)),
                       "sample_locations": dict(list(diagnostics.items())[:12]),
                       "location_keys": dict(Counter(tuple(x.get("raw_fields", [])) for x in diagnostics.values()).most_common(10)) if False else
                       [dict(fields=list(k), count=v) for k,v in Counter(tuple(x.get("raw_fields", [])) for x in diagnostics.values()).most_common(10)]},
                      f, ensure_ascii=False, indent=2)
        self.stdout.write(f"入力 {len(rows_by_id)}件 / 暫定シリーズ {len(output)}件")
        self.stdout.write(f"地域: {dict(Counter(r['region'] for r in output))}")
        self.stdout.write(f"HIGH/MEDIUMかつ地域確定: {sum(r['priority'] != 'LOW' and r['region'] != 'UNKNOWN' for r in output)}件")
        self.stdout.write(f"未取得の会場ID: {len(set(ids) - set(cached))}件 / 除外: {dict(rejected)}")
        self.stdout.write(f"CSV: {all_path}, eventfrog_grouped_priority.csv, eventfrog_grouped_unknown.csv")
        self.stdout.write("DB変更なし")
