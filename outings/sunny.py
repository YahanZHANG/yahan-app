"""晴れの場所をさがす: pick a day, see where in Switzerland it is sunny.

Switzerland is split into about forty weather points. One Open-Meteo call
fetches all of them (cached for a few hours), and every place or event
takes the forecast of its nearest point, so the page costs one request
however many places it lists.
"""

import math
from datetime import timedelta

import requests
from django.core.cache import cache
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .services import weather

# (Japanese name, latitude, longitude): towns spread over the regions,
# valleys and the south, so sunny pockets show up.
WEATHER_POINTS = [
    ("チューリッヒ", 47.37, 8.54), ("ヴィンタートゥール", 47.50, 8.72), ("シャフハウゼン", 47.70, 8.63),
    ("バーゼル", 47.56, 7.59), ("アーラウ", 47.39, 8.05), ("オルテン", 47.35, 7.90),
    ("ザンクトガレン", 47.42, 9.38), ("アッペンツェル", 47.33, 9.41), ("フラウエンフェルト", 47.56, 8.90),
    ("グラールス", 47.04, 9.07), ("ラッパースヴィル", 47.23, 8.82), ("ツーク", 47.17, 8.52),
    ("ルツェルン", 47.05, 8.31), ("エンゲルベルク", 46.82, 8.40), ("アンデルマット", 46.63, 8.59),
    ("シュヴィーツ", 47.02, 8.65), ("ベルン", 46.95, 7.45), ("トゥーン", 46.76, 7.63),
    ("インターラーケン", 46.69, 7.86), ("グリンデルワルト", 46.62, 8.04), ("カンデルシュテーク", 46.49, 7.67),
    ("グシュタード", 46.47, 7.29), ("ビール", 47.14, 7.25), ("ソロトゥルン", 47.21, 7.54),
    ("ヌーシャテル", 46.99, 6.93), ("フリブール", 46.81, 7.15), ("ローザンヌ", 46.52, 6.63),
    ("ジュネーブ", 46.20, 6.15), ("モントルー", 46.43, 6.91), ("イヴェルドン", 46.78, 6.64),
    ("シオン", 46.23, 7.36), ("マルティニ", 46.10, 7.07), ("ブリーク", 46.32, 7.99),
    ("ツェルマット", 46.02, 7.75), ("サース・フェー", 46.11, 7.93), ("ルガーノ", 46.00, 8.95),
    ("ロカルノ", 46.17, 8.80), ("ベリンツォーナ", 46.19, 9.02), ("クール", 46.85, 9.53),
    ("ダボス", 46.80, 9.84), ("サンモリッツ", 46.50, 9.84), ("スクオール", 46.80, 10.30),
    ("ディセンティス", 46.70, 8.85), ("ラークス", 46.81, 9.26), ("ポスキアーヴォ", 46.32, 10.06),
]

POINTS = [(lat, lon) for _, lat, lon in WEATHER_POINTS]


def nearest_point(lat, lon):
    """Index of the closest weather point (flat-earth distance is enough here)."""
    scale = math.cos(math.radians(46.8))
    return min(range(len(POINTS)), key=lambda i: (POINTS[i][0] - lat) ** 2 + ((POINTS[i][1] - lon) * scale) ** 2)


def days_to_pick(now):
    """[(date, label)] for today and the next six days."""
    today = timezone.localdate(now)
    names = {0: "今日", 1: "明日"}
    return [
        (day, f"{names.get(i, '')}{'・' if i in names else ''}{day.month}/{day.day}（{weather.WEEKDAYS_JA[day.weekday()]}）")
        for i, day in ((i, today + timedelta(days=i)) for i in range(7))
    ]


def sun_rank(day):
    """Smaller is sunnier: weather class first, then the chance of rain."""
    if not day or day.get("code") is None:
        return (9, 100)
    code = int(day["code"])
    if code <= 1:
        kind = 0
    elif code == 2:
        kind = 1
    elif code in (3, 45, 48):
        kind = 2
    elif code in (71, 73, 75, 77, 85, 86):
        kind = 4
    else:
        kind = 3
    return (kind, round(day.get("rain") or 0))


def is_sunny(day):
    kind, rain = sun_rank(day)
    return kind <= 1 and rain < 40


def point_forecasts(day):
    """[{name, lat, lon, raw, text, sunny}] for every weather point on `day`."""
    forecasts = weather._forecasts(POINTS)
    rows = []
    for (name, lat, lon), point in zip(WEATHER_POINTS, POINTS):
        raw = forecasts.get(point, {}).get(day.isoformat())
        rows.append({
            "name": name, "lat": lat, "lon": lon, "raw": raw,
            "text": weather.describe(raw), "sunny": is_sunny(raw), "rank": sun_rank(raw),
        })
    return rows


def locate(spot):
    """Coordinates for a 子連れスポット from its town, looked up once and saved."""
    if spot.latitude is not None and spot.longitude is not None:
        return spot.latitude, spot.longitude
    key = f"outings-town:{spot.town.casefold()}:{spot.canton}"
    found = cache.get(key)
    if found is None:
        try:
            response = requests.get(
                weather.GEOCODE_URL,
                params={"name": spot.town, "count": 5, "language": "de", "countryCode": "CH"},
                timeout=weather.TIMEOUT,
            )
            response.raise_for_status()
            results = [r for r in response.json().get("results") or [] if r.get("country_code") == "CH"]
        except (requests.RequestException, ValueError):
            return None
        canton = weather.REGION_NAMES.get(spot.canton, "")
        match = next((r for r in results if canton and r.get("admin1") == canton), results[0] if results else None)
        found = (match["latitude"], match["longitude"]) if match else ()
        cache.set(key, found, 30 * 24 * 60 * 60)
    if not found:
        return None
    spot.latitude, spot.longitude = round(found[0], 5), round(found[1], 5)
    spot.save(update_fields=["latitude", "longitude"])
    return spot.latitude, spot.longitude


# =========================================================
# Page
# =========================================================

MAX_ROWS = 80
MAX_LOOKUPS = 8  # new town or city lookups per page view

WHAT = [("kids", "子連れスポット"), ("trips", "旅行"), ("events", "イベント")]
SPOT_TYPE_EMOJI = {"attractions": "📍", "tours": "🥾", "destinations": "🏘️", "offers": "🎟️"}


RAINY_OK = {"kids", "events"}  # kinds of places that know whether they work in the rain


def _items_kids(day, rainy=False):
    from .spot_views import decorate, published_spots
    items, lookups = [], 0
    for spot in published_spots():
        if not spot.open_in(day.month) or (rainy and not spot.rainy_ok):
            continue
        if spot.latitude is None and lookups < MAX_LOOKUPS:
            lookups += 1
            locate(spot)
        if spot.latitude is None:
            continue
        decorate(spot)
        items.append({
            "title": spot.title, "url": reverse("outings:spot_detail", args=[spot.pk]),
            "sub": f"{spot.get_kind_display()}・{spot.town}", "emoji": spot.emoji,
            "lat": spot.latitude, "lon": spot.longitude, "badges": spot.badges[:3], "image": spot.image_url,
        })
    return items


def _items_trips(day):
    from .tourist_views import tourist_spot_queryset
    spots = tourist_spot_queryset().filter(latitude__isnull=False, longitude__isnull=False).only(
        "pk", "title_ja", "title_original", "spot_type", "latitude", "longitude", "ai_quality_score", "details",
    ).order_by("-ai_quality_score", "pk")[:1500]
    return [{
        "title": (spot.title_ja or spot.title_original).split("｜")[0],
        "url": reverse("outings:tourist_spot_detail", args=[spot.pk]),
        "sub": spot.get_spot_type_display(), "emoji": SPOT_TYPE_EMOJI.get(spot.spot_type, "📍"),
        "lat": float(spot.latitude), "lon": float(spot.longitude), "badges": [],
        "image": ((spot.details or {}).get("approved_image") or {}).get("url", ""),
    } for spot in spots]


def _items_events(day, now, family, rainy=False):
    from .cards import decorate
    from .event_views import is_family, is_one_off, live_events
    items, lookups = [], 0
    for event in live_events(now):
        dates = [d for d in event.upcoming_dates if timezone.localdate(d.start_at) == day]
        if not dates or event.location is None or not is_one_off(event) or (family and not is_family(event)):
            continue
        if rainy and not event.is_indoor:
            continue
        location = event.location
        if location.latitude is None and lookups < MAX_LOOKUPS:
            lookups += 1
            weather.geocode(location)
        if location.latitude is None:
            continue
        decorate(event, now)
        items.append({
            "title": event.title, "url": reverse("outings:event_detail", args=[event.pk]),
            "sub": f"{timezone.localtime(dates[0].start_at):%H:%M}・{location.city}", "emoji": event.display_emoji,
            "lat": float(location.latitude), "lon": float(location.longitude), "badges": [],
            "image": event.image_url,
        })
    return items


def sunny_page(request):
    from .event_views import kids_choice
    from .visitor import get_visitor_id, set_visitor_cookie

    now = timezone.now()
    days = days_to_pick(now)
    day = days[0][0]
    wanted = request.GET.get("day", "")
    for option, _ in days:
        if option.isoformat() == wanted:
            day = option
    kids, _ = kids_choice(request, "kids")
    what = request.GET.get("what", "")
    if what not in dict(WHAT):
        what = "kids" if kids else "trips"

    rainy = what in RAINY_OK and request.GET.get("rainy") == "1"

    points = point_forecasts(day)
    if what == "kids":
        items = _items_kids(day, rainy=rainy)
    elif what == "trips":
        items = _items_trips(day)
    else:
        items = _items_events(day, now, family=kids, rainy=rainy)

    for item in items:
        point = points[nearest_point(item["lat"], item["lon"])]
        item.update(weather=point["text"], rank=point["rank"], sunny=point["sunny"], area=point["name"])
    items.sort(key=lambda item: (item["rank"], item["title"]))

    groups = [
        ("sunny", "☀️ 晴れ", [i for i in items if i["sunny"]]),
        ("cloudy", "⛅ くもり・にわか雨かも", [i for i in items if not i["sunny"] and i["rank"][0] <= 2]),
        ("wet", "☔ 雨・雪", [i for i in items if i["rank"][0] >= 3]),
    ]
    shown = 0
    for index, (key, label, rows) in enumerate(groups):
        room = max(MAX_ROWS - shown, 0)
        groups[index] = {"key": key, "label": label, "rows": rows[:room], "total": len(rows)}
        shown += len(rows[:room])

    has_forecast = any(p["text"] for p in points)
    map_data = {
        "points": [{"name": p["name"], "lat": p["lat"], "lon": p["lon"],
                    "emoji": p["text"]["emoji"] if p["text"] else "", "temp": (p["text"] or {}).get("temp", ""),
                    "sunny": p["sunny"]} for p in points],
        "items": [{"title": i["title"], "url": i["url"], "lat": i["lat"], "lon": i["lon"],
                   "emoji": i["emoji"], "sunny": i["sunny"]} for i in items[:600]],
    }
    sunny_areas = sorted((p for p in points if p["sunny"]), key=lambda p: p["rank"])
    response = render(request, "outings/sunny.html", {
        "day": day,
        "days": [{"label": label, "value": option.isoformat(), "active": option == day} for option, label in days],
        "what": what,
        "whats": [{"key": key, "label": label, "active": key == what} for key, label in WHAT],
        "rainy": rainy,
        "rainy_possible": what in RAINY_OK,
        "groups": groups,
        "count": len(items),
        "sunny_count": groups[0]["total"],
        "sunny_areas": [p["name"] for p in sunny_areas][:8],
        "has_forecast": has_forecast,
        "map_data": map_data,
    })
    return set_visitor_cookie(request, response, get_visitor_id(request))
