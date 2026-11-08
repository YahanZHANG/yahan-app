"""Weather forecast for events, trips and HOME, through Open-Meteo.

Forecasts come from MeteoSwiss's own ICON-CH models (1-2 km grid, the ones
behind the MeteoSwiss app; about 5 days ahead) with Open-Meteo's best model
filling the later days. Open-Meteo is free without an API key for
non-commercial use. Every network failure is silent: the page simply shows
no weather.

A day is described by its weather during the daytime hours still ahead
(a rainy morning does not make a sunny afternoon "rain"). Forecasts are
cached until the next refresh: every hour from 6:00 to 21:00, every three
hours at night (Zurich time).
"""

import logging
from datetime import timedelta
from decimal import Decimal

import requests
from django.core.cache import cache
from django.utils import timezone

from outings.regions import REGION_NAMES


logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

FORECAST_DAYS = 7
# MeteoSwiss first; best_match covers the days after its ~5-day range.
MODELS = ("meteoswiss_icon_seamless", "best_match")
HOURLY = "weather_code,temperature_2m,precipitation_probability"
# Hours that describe a day out.
DAY_HOURS = range(8, 19)
# Fresh forecasts: every hour in the day, every three hours at night.
REFRESH_HOURS = (0, 3) + tuple(range(6, 22))
TIMEOUT = 3
MAX_GEOCODES_PER_REQUEST = 5

# WMO weather codes -> (emoji, Japanese label)
WEATHER_CODES = {
    0: ("☀️", "晴れ"),
    1: ("🌤️", "晴れ"),
    2: ("⛅", "くもり時々晴れ"),
    3: ("☁️", "くもり"),
    # 🌫️ shows as a pale square on many phones: a cloud reads better.
    45: ("☁️", "霧"),
    48: ("☁️", "霧"),
    51: ("🌦️", "霧雨"),
    53: ("🌦️", "霧雨"),
    55: ("🌦️", "霧雨"),
    56: ("🌧️", "着氷性の霧雨"),
    57: ("🌧️", "着氷性の霧雨"),
    61: ("🌧️", "小雨"),
    63: ("🌧️", "雨"),
    65: ("🌧️", "大雨"),
    66: ("🌧️", "着氷性の雨"),
    67: ("🌧️", "着氷性の雨"),
    71: ("🌨️", "小雪"),
    73: ("🌨️", "雪"),
    75: ("❄️", "大雪"),
    77: ("🌨️", "雪"),
    80: ("🌦️", "にわか雨"),
    81: ("🌦️", "にわか雨"),
    82: ("⛈️", "強いにわか雨"),
    85: ("🌨️", "にわか雪"),
    86: ("🌨️", "にわか雪"),
    95: ("⛈️", "雷雨"),
    96: ("⛈️", "雷雨"),
    99: ("⛈️", "雷雨"),
}


def _round(value):
    return round(float(value), 2)


def geocode(location):
    """Return (lat, lon) for a location, geocoding its city once if needed."""
    if location.latitude is not None and location.longitude is not None:
        return float(location.latitude), float(location.longitude)
    key = f"outings-geo:{location.city.casefold()}:{location.canton}"
    found = cache.get(key)
    if found is None:
        try:
            response = requests.get(
                GEOCODE_URL,
                params={"name": location.city, "count": 5, "language": "de", "countryCode": "CH"},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            results = response.json().get("results") or []
        except (requests.RequestException, ValueError) as exc:
            logger.info("Geocoding failed for %s: %s", location.city, exc)
            return None
        # Prefer a place in the same canton ("admin1" is its German name).
        results = [r for r in results if r.get("country_code") == "CH"]
        canton = REGION_NAMES.get(location.canton, "")
        match = next((r for r in results if canton and r.get("admin1") == canton), results[0] if results else None)
        found = (match["latitude"], match["longitude"]) if match else ()
        cache.set(key, found, 30 * 24 * 60 * 60)
    if not found:
        return None
    location.latitude = Decimal(str(round(found[0], 6)))
    location.longitude = Decimal(str(round(found[1], 6)))
    location.save(update_fields=["latitude", "longitude"])
    return found


def cache_seconds(now=None):
    """Seconds until the next refresh time (Zurich): hourly 6-21h, three-hourly at night."""
    local = timezone.localtime(now or timezone.now())
    for days_ahead in (0, 1):
        for hour in REFRESH_HOURS:
            at = (local + timedelta(days=days_ahead)).replace(hour=hour, minute=0, second=0, microsecond=0)
            if at > local:
                return max(60, int((at - local).total_seconds()))
    return 3 * 60 * 60


def _series(block, name, size):
    """One hourly variable, MeteoSwiss where it has a value, the fallback model elsewhere."""
    # Open-Meteo names each model's values "<variable>_<model>"; any other
    # spelling of the same variable is still used, after those.
    keys = [f"{name}_{model}" for model in MODELS] + [name]
    keys += sorted(k for k in block if k.startswith(name) and k not in keys)
    rows = [block[k] for k in keys if isinstance(block.get(k), list)]
    return [next((r[i] for r in rows if i < len(r) and r[i] is not None), None) for i in range(size)]


def _parse_hourly(row):
    """{day: {hour: (code, temp, rain)}} from one location's response."""
    hourly = (row or {}).get("hourly") or {}
    times = hourly.get("time") or []
    codes, temps, rains = (_series(hourly, name, len(times)) for name in HOURLY.split(","))
    result = {}
    for stamp, code, temp, rain in zip(times, codes, temps, rains):
        try:
            result.setdefault(stamp[:10], {})[int(stamp[11:13])] = (code, temp, rain)
        except (TypeError, ValueError):
            continue
    return result


def _request_hourly(points):
    """Hourly forecasts for several (lat, lon) points in one request, or None."""
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": ",".join(str(lat) for lat, _ in points),
                "longitude": ",".join(str(lon) for _, lon in points),
                "hourly": HOURLY, "models": ",".join(MODELS),
                "timezone": "Europe/Zurich", "forecast_days": FORECAST_DAYS + 1,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.info("Forecast failed: %s", exc)
        return None
    rows = data if isinstance(data, list) else [data]
    return [_parse_hourly(row) for row in rows]


def summarize(values):
    """(code, highest temp, lowest temp, highest rain chance) for some hours.

    The weather of most of those hours wins (ties: the worse one), so a
    short shower does not turn a sunny day into a rainy one.
    """
    values = [v for v in values if v[0] is not None]
    if not values:
        return None
    counts = {}
    for v in values:
        counts[int(v[0])] = counts.get(int(v[0]), 0) + 1
    code = max(counts, key=lambda c: (counts[c], SEVERITY.get(c, 0)))
    temps = [v[1] for v in values if v[1] is not None]
    rains = [v[2] for v in values if v[2] is not None]
    return code, (max(temps) if temps else None), (min(temps) if temps else None), (max(rains) if rains else None)


def daily_from_hours(hours, now=None):
    """{day: {code, max, min, rain}}: daytime hours, and only those still ahead today."""
    local = timezone.localtime(now or timezone.now())
    today = local.date().isoformat()
    days = {}
    for day, by_hour in hours.items():
        span = [h for h in DAY_HOURS if day != today or h >= local.hour]
        if day == today and not span:
            span = [h for h in range(local.hour, 24)]  # evening: the rest of today
        found = summarize([by_hour[h] for h in span if h in by_hour])
        if found:
            code, high, low, rain = found
            days[day] = {"code": code, "max": high, "min": low, "rain": rain}
    return days


def _fetch(points):
    """Daily forecasts for several (lat, lon) points in one request."""
    rows = _request_hourly(points)
    if rows is None:
        return {}
    return {point: daily_from_hours(hours) for point, hours in zip(points, rows)}


def describe(day):
    if not day or day.get("code") is None:
        return None
    emoji, label = WEATHER_CODES.get(int(day["code"]), ("🌡️", ""))
    text = {"emoji": emoji, "label": label}
    if day.get("max") is not None and day.get("min") is not None:
        text["temp"] = f"{round(day['max'])}° / {round(day['min'])}°"
    if day.get("rain") is not None:
        text["rain"] = f"{round(day['rain'])}%"
    return text


def attach(events, now=None):
    """Set `event.weather` on events whose next date is within the forecast range."""
    now = now or timezone.now()
    limit = timezone.localdate(now) + timedelta(days=FORECAST_DAYS)
    wanted = []
    geocoded = 0
    for event in events:
        event.weather = None
        occurrence = getattr(event, "next_occurrence", None)
        if occurrence is None or event.location is None:
            continue
        # A run that is already open is described by today's weather.
        day = max(timezone.localdate(occurrence.start_at), timezone.localdate(now))
        if day > limit:
            continue
        has_coords = event.location.latitude is not None and event.location.longitude is not None
        if not has_coords:
            if geocoded >= MAX_GEOCODES_PER_REQUEST:
                continue
            geocoded += 1
        coords = geocode(event.location)
        if not coords:
            continue
        wanted.append((event, (_round(coords[0]), _round(coords[1])), day.isoformat()))
    if not wanted:
        return events

    forecasts = _forecasts(point for _, point, _ in wanted)
    for event, point, day in wanted:
        event.weather = describe(forecasts.get(point, {}).get(day))
    return events


WEEKDAYS_JA = "月火水木金土日"


def weekend_days(now=None):
    """This week's Saturday and Sunday (only Sunday when today is Sunday)."""
    today = timezone.localdate(now or timezone.now())
    if today.weekday() == 6:
        return [today]
    saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    return [saturday, saturday + timedelta(days=1)]


def _forecasts(points):
    """Cached daily forecasts for (lat, lon) points, fetching the missing ones together."""
    forecasts, missing = {}, []
    for point in dict.fromkeys(points):
        hit = cache.get(f"outings-wx:{point[0]}:{point[1]}")
        if hit is None:
            missing.append(point)
        else:
            forecasts[point] = hit
    if missing:
        ttl = cache_seconds()
        for point, days in _fetch(missing).items():
            cache.set(f"outings-wx:{point[0]}:{point[1]}", days, ttl)
            forecasts[point] = days
    return forecasts


# Morning and afternoon on HOME: hours that count for each half.
HALVES = (("午前", range(8, 12)), ("午後", range(12, 18)))
# Ties between equally common weathers go to the worse one (rain over sun).
SEVERITY = {code: rank for rank, code in enumerate([0, 1, 2, 3, 45, 48, 51, 53, 55, 80, 61, 63, 81, 71, 73, 85, 77, 56, 57, 66, 67, 65, 75, 86, 82, 95, 96, 99])}


def _fetch_hourly(point):
    rows = _request_hourly([point])
    return rows[0] if rows else None


def half_days(point, days):
    """[{day, date, halves: [{name, emoji, label, temp, rain}]}] for each day, morning and afternoon."""
    key = f"outings-wx-hourly:{point[0]}:{point[1]}"
    hours = cache.get(key)
    if hours is None:
        hours = _fetch_hourly(point)
        if hours is None:
            return []
        cache.set(key, hours, cache_seconds())
    rows = []
    for day in days:
        by_hour = hours.get(day.isoformat()) or {}
        halves = []
        for name, span in HALVES:
            found = summarize([by_hour[h] for h in span if h in by_hour])
            if not found:
                continue
            code, high, _, rain = found
            emoji, label = WEATHER_CODES.get(code, ("🌡️", ""))
            halves.append({
                "name": name, "emoji": emoji, "label": label,
                "temp": round(high) if high is not None else None, "rain": round(rain) if rain is not None else None,
            })
        if halves:
            rows.append({"day": WEEKDAYS_JA[day.weekday()], "date": f"{day.month}/{day.day}", "halves": halves})
    return rows


def attach_weekend(spots, now=None):
    """Set `spot.weekend_weather` to [{day, emoji, label, temp, rain}, ...] for trips with coordinates."""
    days = weekend_days(now)
    wanted = []
    for spot in spots:
        spot.weekend_weather = None
        if spot.latitude is None or spot.longitude is None:
            continue
        wanted.append((spot, (_round(spot.latitude), _round(spot.longitude))))
    if not wanted:
        return spots
    forecasts = _forecasts(point for _, point in wanted)
    for spot, point in wanted:
        rows = []
        for day in days:
            text = describe(forecasts.get(point, {}).get(day.isoformat()))
            if text:
                rows.append({"day": WEEKDAYS_JA[day.weekday()], **text})
        spot.weekend_weather = rows or None
    return spots
