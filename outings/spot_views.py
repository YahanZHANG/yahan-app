"""子連れスポット and the family HOME.

Spots are places families can visit any day, written by hand. Filters are
plain links like the event list, so every state has its own URL.
"""

import random

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .event_views import is_family_event, live_events, querystring
from .cards import decorate as decorate_event
from .models import FamilySpot
from .regions import AREA_OF_CANTON, AREAS, REGION_NAMES_JA
from .services import weather
from .visitor import get_visitor_id, set_visitor_cookie


KIND_EMOJI = {
    "park": "🛝", "animals": "🦒", "museum": "🦖", "indoor": "🤸",
    "nature": "🌲", "mountain": "🚠", "water": "🏊", "farm": "🎃",
    "history": "🏰", "theme": "🎡", "other": "✈️",
}

LANGUAGE_MARK = {"none": "◎", "little": "○", "helps": "△"}

# (key, label, lowest age, highest age)
AGE_GROUPS = [
    ("0", "0〜2歳", 0, 2),
    ("3", "3〜5歳", 3, 5),
    ("6", "6〜9歳", 6, 9),
    ("10", "10歳〜", 10, 18),
]

# (key, label, icon) of the yes/no filters.
TOGGLES = [
    ("rainy", "雨の日OK", "bi-umbrella"),
    ("easy", "言葉なしでOK", "bi-emoji-smile"),
    ("free", "無料あり", "bi-cash-coin"),
    ("now", "いま開いている季節", "bi-calendar-check"),
]

TRIPS = [("day", "日帰り"), ("overnight", "1泊")]

# Zurich: the weekend weather shown on HOME.
HOME_POINT = (47.37, 8.54)


def published_spots():
    return FamilySpot.objects.filter(status=FamilySpot.Status.PUBLISHED)


def decorate(spot):
    """Emoji and short badges shown on cards and the detail page."""
    spot.emoji = spot.emoji or KIND_EMOJI.get(spot.kind, "🎈")
    spot.area_label = dict((key, label) for key, label, _ in AREAS).get(AREA_OF_CANTON.get(spot.canton), "")
    badges = []
    if spot.age_label:
        badges.append((spot.age_label, "age"))
    if spot.language in ("none", "little"):
        badges.append(("言葉なしでOK", "ok"))
    if spot.rainy_ok:
        badges.append(("雨の日OK", "family"))
    if spot.price == FamilySpot.Price.FREE:
        badges.append(("無料", "free"))
    elif spot.price == FamilySpot.Price.PARTLY:
        badges.append(("無料あり", "free"))
    if spot.trip == FamilySpot.Trip.OVERNIGHT:
        badges.append(("1泊がおすすめ", "trip"))
    spot.badges = badges
    spot.language_mark = LANGUAGE_MARK.get(spot.language, "")
    return spot


def filter_spots(spots, *, area="", age="", kind="", trip="", rainy=False, easy=False, free=False, now=False, month=None):
    if kind:
        spots = spots.filter(kind=kind)
    if area:
        spots = spots.filter(canton__in=dict((key, codes) for key, _, codes in AREAS).get(area, ()))
    if rainy:
        spots = spots.filter(rainy_ok=True)
    if easy:
        spots = spots.filter(language__in=["none", "little"])
    if free:
        spots = spots.exclude(price=FamilySpot.Price.PAID)
    if trip == "day":
        spots = spots.exclude(trip=FamilySpot.Trip.OVERNIGHT)
    elif trip == "overnight":
        spots = spots.exclude(trip=FamilySpot.Trip.DAY)
    spots = list(spots)
    group = next((g for g in AGE_GROUPS if g[0] == age), None)
    if group:
        _, _, low, high = group
        spots = [
            s for s in spots
            if (s.age_min is None or s.age_min <= high) and (s.age_max is None or s.age_max >= low)
        ]
    if now:
        spots = [s for s in spots if s.open_in(month)]
    return spots


def spot_list(request):
    get = request.GET
    kind = get.get("kind", "")
    if kind not in FamilySpot.Kind.values:
        kind = ""
    area = get.get("area", "")
    if area not in {key for key, _, _ in AREAS}:
        area = ""
    age = get.get("age", "")
    if age not in {key for key, *_ in AGE_GROUPS}:
        age = ""
    trip = get.get("trip", "")
    if trip not in dict(TRIPS):
        trip = ""
    flags = {key: get.get(key) == "1" for key, _, _ in TOGGLES}
    month = timezone.localdate().month

    spots = [decorate(s) for s in filter_spots(
        published_spots(), area=area, age=age, kind=kind, trip=trip, month=month, **flags,
    )]
    # Places open this season first.
    spots.sort(key=lambda s: not s.open_in(month))

    params = {"kids": "1", "kind": kind, "area": area, "age": age, "trip": trip,
              **{key: "1" if on else "" for key, on in flags.items()}}

    def link(**changes):
        return querystring(params, **changes)

    def choice(name, value, current):
        return link(**{name: "" if value == current else value})

    used_kinds = set(published_spots().values_list("kind", flat=True))
    used_areas = {AREA_OF_CANTON.get(c) for c in published_spots().values_list("canton", flat=True)}
    chips = {
        "toggles": [
            {"label": label, "icon": icon, "active": flags[key], "qs": link(**{key: "" if flags[key] else "1"})}
            for key, label, icon in TOGGLES
        ],
        "ages": [{"label": label, "active": key == age, "qs": choice("age", key, age)} for key, label, *_ in AGE_GROUPS],
        "trips": [{"label": label, "active": key == trip, "qs": choice("trip", key, trip)} for key, label in TRIPS],
        "areas": [
            {"label": label, "active": key == area, "qs": choice("area", key, area)}
            for key, label, _ in AREAS if key in used_areas
        ],
        "kinds": [
            {"label": label, "emoji": KIND_EMOJI.get(value, "🎈"), "active": value == kind, "qs": choice("kind", value, kind)}
            for value, label in FamilySpot.Kind.choices if value in used_kinds
        ],
    }
    filtered = bool(kind or area or age or trip or any(flags.values()))
    return render(request, "outings/spot_list.html", {
        "spots": spots,
        "chips": chips,
        "filtered": filtered,
        "filter_count": sum(bool(v) for v in (kind, area, age, trip)) + sum(flags.values()),
        "clear_qs": "kids=1",
    })


def spot_list_redirect(request):
    """Old /outings/spots/ links: the list now lives under 旅行 with 子連れ ticked."""
    query = request.GET.copy()
    query["kids"] = "1"
    return redirect(reverse("outings:tourist_spot_list") + "?" + query.urlencode())


def spot_detail(request, pk):
    spot = decorate(get_object_or_404(published_spots(), pk=pk))
    others = [decorate(s) for s in published_spots().exclude(pk=spot.pk).filter(kind=spot.kind)[:3]]
    if len(others) < 3:
        nearby = published_spots().exclude(pk__in=[spot.pk] + [o.pk for o in others]).filter(
            canton__in=dict((k, c) for k, _, c in AREAS).get(AREA_OF_CANTON.get(spot.canton), ()),
        )[: 3 - len(others)]
        others += [decorate(s) for s in nearby]
    return render(request, "outings/spot_detail.html", {
        "spot": spot,
        "others": others,
        "season_months": spot.get_season_display(),
    })


# =========================================================
# HOME
# =========================================================

def weekend_events(now, limit=6):
    days = {d.isoformat() for d in weather.weekend_days(now)}
    picked = []
    for event in live_events(now):
        if not is_family_event(event):
            continue
        decorate_event(event, now)
        dates = [d for d in event.upcoming_dates if timezone.localdate(d.start_at).isoformat() in days]
        if dates:
            event.weekend_start = dates[0].start_at
            picked.append(event)
    # Language-free events first, then by time.
    picked.sort(key=lambda e: (e.language_barrier not in ("none", "japanese"), e.weekend_start))
    return picked[:limit]


def weekend_forecast(now):
    """[{day, emoji, label, temp, rain}] for Zurich this weekend, and whether rain is likely."""
    forecasts = weather._forecasts([HOME_POINT])
    rows = []
    rainy = False
    for day in weather.weekend_days(now):
        raw = forecasts.get(HOME_POINT, {}).get(day.isoformat())
        text = weather.describe(raw)
        if text:
            rows.append({"day": weather.WEEKDAYS_JA[day.weekday()], **text})
            if (raw.get("rain") or 0) >= 60:
                rainy = True
    return rows, rainy


def weekly_pick(spots, count, now):
    """A different handful each week, the same all week long."""
    week = timezone.localdate(now).isocalendar()
    spots = list(spots)
    random.Random(f"{week[0]}-{week[1]}").shuffle(spots)
    return spots[:count]


def home(request):
    now = timezone.now()
    month = timezone.localdate(now).month
    forecast, rainy = weekend_forecast(now)

    open_now = [s for s in published_spots() if s.open_in(month)]
    day_spots = [s for s in open_now if s.trip != FamilySpot.Trip.OVERNIGHT]
    if rainy:
        # Rain: indoor places first.
        day_spots = [s for s in day_spots if s.rainy_ok] + [s for s in day_spots if not s.rainy_ok]
        weekend_spots = day_spots[:6]
    else:
        weekend_spots = weekly_pick(day_spots, 6, now)
    overnight = weekly_pick([s for s in open_now if s.trip != FamilySpot.Trip.DAY], 6, now)

    quick = [
        {"label": "雨の日OK", "emoji": "☔", "qs": "rainy=1"},
        {"label": "言葉なしでOK", "emoji": "😊", "qs": "easy=1"},
        {"label": "無料あり", "emoji": "🆓", "qs": "free=1"},
        {"label": "日帰り", "emoji": "🚆", "qs": "trip=day"},
    ] + [{"label": label, "emoji": "", "qs": f"age={key}"} for key, label, *_ in AGE_GROUPS]

    visitor_id = get_visitor_id(request)
    response = render(request, "outings/home.html", {
        "forecast": forecast,
        "rainy": rainy,
        "weekend_spots": [decorate(s) for s in weekend_spots],
        "weekend_events": weekend_events(now),
        "overnight_spots": [decorate(s) for s in overnight],
        "quick_filters": quick,
        "spot_count": published_spots().count(),
        "region_names": REGION_NAMES_JA,
    })
    return set_visitor_cookie(request, response, visitor_id)
