"""Daily weather forecast for an event's date and place, from Open-Meteo.

Open-Meteo is free without an API key for non-commercial use. Forecasts are
reliable for about a week, so only dates within FORECAST_DAYS are looked up.
Every network failure is silent: the page simply shows no weather.

City coordinates are geocoded once and saved on EventLocation; forecasts are
fetched in one request for all places on a page and cached for a few hours.
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
CACHE_SECONDS = 3 * 60 * 60
TIMEOUT = 3
MAX_GEOCODES_PER_REQUEST = 5

# WMO weather codes -> (emoji, Japanese label)
WEATHER_CODES = {
    0: ("☀️", "晴れ"),
    1: ("🌤️", "晴れ"),
    2: ("⛅", "くもり時々晴れ"),
    3: ("☁️", "くもり"),
    45: ("🌫️", "霧"),
    48: ("🌫️", "霧"),
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


def _fetch(points):
    """Daily forecasts for several (lat, lon) points in one request."""
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": ",".join(str(lat) for lat, _ in points),
                "longitude": ",".join(str(lon) for _, lon in points),
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "Europe/Zurich",
                "forecast_days": FORECAST_DAYS + 1,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.info("Forecast failed: %s", exc)
        return {}
    rows = data if isinstance(data, list) else [data]
    result = {}
    for point, row in zip(points, rows):
        daily = (row or {}).get("daily") or {}
        days = {}
        for i, day in enumerate(daily.get("time") or []):
            try:
                days[day] = {
                    "code": daily["weather_code"][i],
                    "max": daily["temperature_2m_max"][i],
                    "min": daily["temperature_2m_min"][i],
                    "rain": daily.get("precipitation_probability_max", [None] * (i + 1))[i],
                }
            except (KeyError, IndexError, TypeError):
                continue
        result[point] = days
    return result


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

    forecasts, missing = {}, []
    for point in dict.fromkeys(point for _, point, _ in wanted):
        hit = cache.get(f"outings-wx:{point[0]}:{point[1]}")
        if hit is None:
            missing.append(point)
        else:
            forecasts[point] = hit
    if missing:
        for point, days in _fetch(missing).items():
            cache.set(f"outings-wx:{point[0]}:{point[1]}", days, CACHE_SECONDS)
            forecasts[point] = days
    for event, point, day in wanted:
        event.weather = describe(forecasts.get(point, {}).get(day))
    return events
