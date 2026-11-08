"""子連れスポット and the family HOME.

Spots are places families can visit any day, written by hand. Filters are
plain links like the event list, so every state has its own URL.
"""

import random

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from . import profile as visitor_profile
from .event_views import is_family_event, is_one_off, live_events, querystring
from .cards import decorate as decorate_event
from .models import FamilySpot, OutingsPreference
from .profile import AGE_GROUPS
from .regions import AREA_OF_CANTON, AREAS, REGION_NAMES_JA
from .services import weather
from .visitor import get_visitor_id, set_visitor_cookie


KIND_EMOJI = {
    "park": "🛝", "animals": "🦒", "museum": "🦖", "indoor": "🤸",
    "nature": "🌲", "mountain": "🚠", "water": "🏊", "farm": "🎃",
    "history": "🏰", "theme": "🎡", "other": "✈️",
}

LANGUAGE_MARK = {"none": "◎", "little": "○", "helps": "△"}


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
    from .map_points import kids_point, map_response, wants_map
    if wants_map(request):
        from .sunny import MAX_LOOKUPS, locate
        for spot in [s for s in spots if s.latitude is None][:MAX_LOOKUPS]:
            locate(spot)  # town lookup, saved once
        return map_response([kids_point(s) for s in spots])

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
            {"key": key, "label": label, "icon": icon, "active": flags[key], "qs": link(**{key: "" if flags[key] else "1"})}
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
    # The filter form: pick everything, then press 探す once.
    groups = [
        {"name": "age", "title": "年齢", "value": age, "options": [(key, label) for key, label, *_ in AGE_GROUPS]},
        {"name": "trip", "title": "チューリッヒから", "value": trip, "options": list(TRIPS)},
        {"name": "area", "title": "地域", "value": area,
         "options": [(key, label) for key, label, _ in AREAS if key in used_areas]},
        {"name": "kind", "title": "種類", "value": kind,
         "options": [(value, f"{KIND_EMOJI.get(value, '🎈')} {label}") for value, label in FamilySpot.Kind.choices if value in used_kinds]},
    ]
    groups = [g for g in groups if len(g["options"]) > 1]
    filtered = bool(kind or area or age or trip or any(flags.values()))
    return render(request, "outings/spot_list.html", {
        "spots": spots,
        "chips": chips,
        "groups": groups,
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
    from .visitor import get_visitor_id, set_visitor_cookie
    from .visits import Target, visit_context
    visitor_id = get_visitor_id(request)
    days = visitor_profile.days_off(timezone.now(), visitor_profile.get_profile(visitor_id))
    wx = []
    if spot.latitude is not None:
        from . import sunny
        wx = place_weather(spot.latitude, spot.longitude, days, weather._forecasts(sunny.POINTS))
    response = render(request, "outings/spot_detail.html", {
        "spot": spot,
        "wx": wx,
        "others": others,
        "season_months": spot.get_season_display(),
        "visits": visit_context(request, Target.KIDS, spot, visitor_id),
    })
    return set_visitor_cookie(request, response, visitor_id)


# =========================================================
# HOME
# =========================================================

def weekend_events(now, limit=6, days=None, family=True, cantons=()):
    days = {d.isoformat() for d in (days or weather.weekend_days(now))}
    picked = []
    for event in live_events(now):
        if not (is_family_event(event) if family else is_one_off(event)):
            continue
        decorate_event(event, now)
        dates = [d for d in event.upcoming_dates if timezone.localdate(d.start_at).isoformat() in days]
        if dates:
            event.weekend_start = dates[0].start_at
            picked.append(event)
    # Nearby first, then language-free, then by time.
    picked.sort(key=lambda e: (
        bool(cantons) and not (e.location and e.location.canton in cantons),
        e.language_barrier not in ("none", "japanese"),
        e.weekend_start,
    ))
    return picked[:limit]


def weekend_forecast(now, days=None, point=HOME_POINT):
    """[{day, emoji, label, temp, rain}] at `point` on the days off, and whether rain is likely."""
    forecasts = weather._forecasts([point])
    rows = []
    rainy = False
    for day in (days or weather.weekend_days(now))[:3]:
        raw = forecasts.get(point, {}).get(day.isoformat())
        text = weather.describe(raw)
        if text:
            rows.append({
                "day": weather.WEEKDAYS_JA[day.weekday()], "date": f"{day.month}/{day.day}", **text,
                "high": round(raw["max"]) if raw.get("max") is not None else None,
                "low": round(raw["min"]) if raw.get("min") is not None else None,
            })
            if (raw.get("rain") or 0) >= 60:
                rainy = True
    return rows, rainy


def place_weather(lat, lon, days, forecasts):
    """[{day, emoji, temp, rank}] at the nearest weather point for each day off."""
    from . import sunny
    if lat is None or lon is None:
        return []
    point = sunny.POINTS[sunny.nearest_point(float(lat), float(lon))]
    rows = []
    for day in days[:2]:
        raw = forecasts.get(point, {}).get(day.isoformat())
        text = weather.describe(raw)
        if text:
            rows.append({
                "day": weather.WEEKDAYS_JA[day.weekday()], "emoji": text["emoji"],
                "temp": text.get("temp", "").split(" ")[0], "rank": sunny.sun_rank(raw),
            })
    return rows


def with_event_weather(events, forecasts):
    for event in events:
        location = event.location
        day = timezone.localdate(event.weekend_start)
        rows = place_weather(location.latitude, location.longitude, [day], forecasts) if location else []
        event.wx = rows[0] if rows else None
    return events


def weather_class(rows, works_in_rain=False):
    """0 sunny ... 4 snow on the best day off; places that work in the rain count as fine."""
    if not rows:
        return 1
    best = min(row["rank"][0] for row in rows)
    return min(best, 1) if works_in_rain else best


def weekly_pick(spots, count, now):
    """A different handful each week, the same all week long."""
    week = timezone.localdate(now).isocalendar()
    spots = list(spots)
    random.Random(f"{week[0]}-{week[1]}").shuffle(spots)
    return spots[:count]


def home(request):
    now = timezone.now()
    month = timezone.localdate(now).month
    visitor_id = get_visitor_id(request)
    preference = visitor_profile.get_profile(visitor_id)
    days = visitor_profile.days_off(now, preference)
    weekday = bool(preference and preference.days_off == OutingsPreference.DaysOff.WEEKDAY)
    from . import find_views
    # The weather row: around the visitor's first area, else Zurich.
    area = (preference.areas or [None])[0] if preference else None
    point = find_views.AREA_CENTRES.get(area, HOME_POINT)
    forecast, _ = weekend_forecast(now, days, point)
    halves = weather.half_days(point, days[:2]) if days else []
    from .visits import hidden_keys
    picks, events, overnight, mode = find_views.home_picks(
        preference, now, days, hide=hidden_keys(request, visitor_id, preference),
    )
    hero = next((i for i in picks if i["image"]), None)
    sunny_names = find_views.sunny_area_names(days) if mode == "sunny" else []
    kids = visitor_profile.wants_kids(preference)
    area_label = dict((k, l) for k, l, _ in AREAS).get(area, "チューリッヒ周辺")

    response = render(request, "outings/home.html", {
        "halves": halves, "forecast": forecast,
        "forecast_area": area_label,
        "mode": mode,
        "sunny_names": sunny_names[:4],
        "weekday": weekday,
        "kids": kids is not False,
        "ask": not (preference and preference.setup),
        "personal": bool(preference and preference.setup == "done"),
        "profile": profile_form_context(preference),
        "picks": picks,
        "hero": hero,
        "events": events,
        "overnight": overnight,
    })
    return set_visitor_cookie(request, response, visitor_id)


# =========================================================
# 「あなたに合わせる」
# =========================================================

def profile_form_context(preference):
    """Choices and current answers for the four questions."""
    return {
        "preference": preference,
        "areas": [(key, label, key in (preference.areas if preference else [])) for key, label, _ in AREAS],
        "german": [(v, l, preference is not None and preference.german == v) for v, l in OutingsPreference.German.choices],
        "kids": preference.with_kids if preference else None,
        "ages": [(k, l, k in (preference.kid_ages if preference else [])) for k, l, *_ in AGE_GROUPS],
        "days": [(v, l, preference is not None and preference.days_off == v) for v, l in OutingsPreference.DaysOff.choices],
        "hide_went": bool(preference and preference.hide_went),
    }


def _safe_next(request, default):
    target = request.POST.get("next", "")
    return target if target.startswith("/outings/") else default


@require_POST
def profile_save(request):
    visitor_id = get_visitor_id(request)
    preference, _ = OutingsPreference.objects.get_or_create(visitor_id=visitor_id)
    if request.POST.get("skip"):
        preference.setup = OutingsPreference.Setup.SKIPPED
        preference.save(update_fields=["setup", "updated_at"])
    else:
        visitor_profile.save_answers(preference, request.POST)
    target = reverse("outings:home") if request.POST.get("skip") else _safe_next(request, reverse("outings:home"))
    response = redirect(target)
    if preference.with_kids is not None:
        # The 子連れ tick follows the answer until it is changed by hand.
        response.delete_cookie("outings_kids")
    return set_visitor_cookie(request, response, visitor_id)
