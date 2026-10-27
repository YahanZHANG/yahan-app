"""
HOME の上に出す「為替・天気」の細いバー。

為替: Frankfurter（欧州中央銀行の公開レート、無料・キー不要、平日1日1回更新）
天気: Open-Meteo（無料・キー不要。おでかけアプリと同じ）

どちらもサーバー側でしばらくためておき、取れないときは何も出さない
（ページが遅くなったり、エラーになったりしないように）。
"""

import logging
from datetime import timedelta

import requests
from django.core.cache import cache
from django.utils import timezone

from outings.services.weather import WEATHER_CODES


logger = logging.getLogger(__name__)

FX_URL = "https://api.frankfurter.dev/v1/{start}.."
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

FX_CACHE_SECONDS = 60 * 60
WEATHER_CACHE_SECONDS = 30 * 60
TIMEOUT = 3

FX_CURRENCIES = ["JPY", "EUR", "USD"]

DEFAULT_REGION = "zurich"
MAX_REGIONS = 2

# 暮らしのお知らせの地域（news/region_classifier.py）の中心の座標
REGION_COORDS = {
    "zurich": (47.3769, 8.5417),
    "winterthur": (47.4988, 8.7237),
    "geneva": (46.2044, 6.1432),
    "basel": (47.5596, 7.5886),
    "lausanne-vaud": (46.5197, 6.6323),
    "bern": (46.9480, 7.4474),
    "lucerne": (47.0502, 8.3093),
    "st-gallen": (47.4245, 9.3767),
    "lugano-ticino": (46.0037, 8.9511),
    "zug": (47.1662, 8.5155),
    "biel-bienne": (47.1368, 7.2468),
    "fribourg": (46.8065, 7.1620),
    "neuchatel": (46.9900, 6.9293),
    "thun": (46.7580, 7.6280),
    "chur-graubuenden": (46.8508, 9.5320),
    "sion-valais": (46.2331, 7.3606),
    "aarau-aargau": (47.3925, 8.0444),
    "schaffhausen": (47.6959, 8.6345),
    "solothurn": (47.2088, 7.5323),
}

WEEKDAYS = "月火水木金土日"

HOURLY_COUNT = 12


def weather_slugs(slugs):
    """天気を出す地域（座標があるものの最初の2つ。なければチューリッヒ）。"""

    picked = []

    for slug in slugs or []:
        if slug in REGION_COORDS and slug not in picked:
            picked.append(slug)
        if len(picked) == MAX_REGIONS:
            break

    return picked or [DEFAULT_REGION]


def fx_rates():
    """
    1 CHF あたりの JPY・EUR・USD と、前の営業日からの変化（%）。
    {"date": "2026-10-26", "rates": {"JPY": {"rate": 172.4, "change": 0.3}, ...}}
    """

    cached = cache.get("news-info-fx")

    if cached is not None:
        return cached or None

    data = {}

    try:
        start = (timezone.localdate() - timedelta(days=7)).isoformat()
        response = requests.get(
            FX_URL.format(start=start),
            params={"base": "CHF", "symbols": ",".join(FX_CURRENCIES)},
            timeout=TIMEOUT,
        )
        response.raise_for_status()

        days = response.json()["rates"]
        dates = sorted(days)
        latest = days[dates[-1]]
        previous = days[dates[-2]] if len(dates) > 1 else None

        rates = {}

        for code in FX_CURRENCIES:
            rate = float(latest[code])
            change = None
            if previous and previous.get(code):
                change = round((rate / float(previous[code]) - 1) * 100, 1)
            rates[code] = {"rate": rate, "change": change}

        data = {"date": dates[-1], "rates": rates}

    except (requests.RequestException, KeyError, ValueError, IndexError, TypeError) as error:
        logger.warning("FX rates unavailable: %s", error)

    # 失敗したときも少しのあいだは問い合わせない
    cache.set("news-info-fx", data, FX_CACHE_SECONDS if data else 10 * 60)

    return data or None


def weather(slugs):
    """
    地域ごとの今の天気と3日分の予報。
    [{"slug", "temp", "emoji", "label", "days": [{"label", "emoji", "max", "min"}]}]
    """

    slugs = weather_slugs(slugs)
    key = "news-info-weather:" + ",".join(slugs)
    cached = cache.get(key)

    if cached is not None:
        return cached

    result = []

    try:
        response = requests.get(
            WEATHER_URL,
            params={
                "latitude": ",".join(str(REGION_COORDS[slug][0]) for slug in slugs),
                "longitude": ",".join(str(REGION_COORDS[slug][1]) for slug in slugs),
                "current": "temperature_2m,weather_code",
                "hourly": "temperature_2m,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "Europe/Zurich",
                "forecast_days": 3,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()

        places = response.json()

        # 1か所だと辞書、複数だとリストで返ってくる
        if isinstance(places, dict):
            places = [places]

        for slug, place in zip(slugs, places):
            current = place["current"]
            emoji, label = WEATHER_CODES.get(current["weather_code"], ("🌡️", ""))
            daily = place["daily"]

            days = []
            for index, day in enumerate(daily["time"]):
                day_emoji, day_label = WEATHER_CODES.get(daily["weather_code"][index], ("🌡️", ""))
                date = timezone.datetime.fromisoformat(day).date()
                days.append({
                    "label": ["今日", "明日"][index] if index < 2 else f"{date.month}/{date.day}（{WEEKDAYS[date.weekday()]}）",
                    "emoji": day_emoji,
                    "text": day_label,
                    "max": round(daily["temperature_2m_max"][index]),
                    "min": round(daily["temperature_2m_min"][index]),
                })

            # 今の時間から12時間分（時刻はスイス時間の "2026-10-27T08:00"）
            now_hour = current["time"][:13]
            hourly = place["hourly"]
            hours = []
            for index, time in enumerate(hourly["time"]):
                if time[:13] < now_hour:
                    continue
                hour_emoji, _ = WEATHER_CODES.get(hourly["weather_code"][index], ("🌡️", ""))
                hours.append({
                    "label": "今" if not hours else f"{int(time[11:13])}時",
                    "emoji": hour_emoji,
                    "temp": round(hourly["temperature_2m"][index]),
                })
                if len(hours) == HOURLY_COUNT:
                    break

            result.append({
                "slug": slug,
                "temp": round(current["temperature_2m"]),
                "emoji": emoji,
                "label": label,
                "hours": hours,
                "days": days,
            })

    except (requests.RequestException, KeyError, ValueError, IndexError, TypeError) as error:
        logger.warning("Weather unavailable: %s", error)
        result = []

    cache.set(key, result, WEATHER_CACHE_SECONDS if result else 10 * 60)

    return result


def info_bar(slugs=None):
    """テンプレートとJSONの両方で使う形にまとめる。"""

    from news.models import Region

    # 選んだ地域は、設定画面の並び順で最初の2つを使う
    order = dict(
        Region.objects
        .filter(slug__in=slugs or [])
        .values_list("slug", "display_order")
    )
    slugs = sorted(
        slugs or [],
        key=lambda slug: (order.get(slug, 9999), slug),
    )

    places = weather(slugs)
    names = dict(
        Region.objects
        .filter(slug__in=[place["slug"] for place in places])
        .values_list("slug", "name")
    )

    for place in places:
        place["name"] = names.get(place["slug"], place["slug"])

    return {
        "fx": fx_rates(),
        "weather": places,
    }
