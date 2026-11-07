"""さがす: one page for events, trips and 子連れスポット with the same
conditions (いつ・どこ・誰と・条件), the forecast for the chosen day on every
card, and a map of the results. Replaces the separate event, trip, sunny and
search lists (their URLs redirect here)."""

import math
import re
from datetime import datetime, time, timedelta

from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from . import profile as visitor_profile
from . import sunny
from .services import schedule
from .cards import decorate as decorate_event
from .event_views import is_family, is_one_off, kids_choice, live_events, remember_kids
from .map_points import MAX_POINTS
from .models import FamilySpot, OutingsVisit
from .profile import AGE_GROUPS
from .regions import AREA_OF_CANTON, AREAS
from .services import search as text_search
from .services import weather
from .spot_views import decorate as decorate_spot
from .spot_views import published_spots
from .visitor import get_visitor_id, set_visitor_cookie
from .visits import MEMBER_RATINGS_NEEDED, ratings, stars_text

PAGE_SIZE = 24

TYPES = [("all", "すべて"), ("event", "イベント"), ("trip", "旅行"), ("kids", "子連れスポット")]
WHEN = [("weekend", "今週末"), ("today", "今日"), ("tomorrow", "明日"), ("any", "いつでも")]
SORTS = [("recommended", "おすすめ順"), ("sunny", "☀️ 晴れ優先"), ("date", "日付順")]
CONDITIONS = [("free", "無料"), ("rainy", "雨でもOK"), ("easy", "言葉なしでOK")]

# Rough centres of the areas, for trips (which have coordinates but no canton).
AREA_CENTRES = {
    "zurich": (47.40, 8.60), "east": (46.90, 9.60), "central": (46.95, 8.30), "bern": (46.95, 7.45),
    "basel": (47.50, 7.65), "west": (46.50, 6.80), "ticino": (46.20, 8.95),
}

WX_CLASS = {0: "sunny", 1: "sunny", 2: "cloudy", 3: "wet", 4: "wet"}


def area_of_point(lat, lon):
    if lat is None or lon is None:
        return ""
    scale = math.cos(math.radians(46.8))
    return min(AREA_CENTRES, key=lambda k: (AREA_CENTRES[k][0] - lat) ** 2 + ((AREA_CENTRES[k][1] - lon) * scale) ** 2)


def event_ages(event):
    """(min, max) from the AI's age note, e.g. 「6歳以上」 -> (6, None)."""
    note = str((event.ai_details or {}).get("age_note") or "")
    numbers = [int(n) for n in re.findall(r"\d+", note)][:2]
    if not numbers:
        return None, None
    if len(numbers) == 2:
        return min(numbers), max(numbers)
    if re.search(r"以下|まで|未満", note):
        return None, numbers[0]
    return numbers[0], None


def ages_fit(low, high, group):
    _, _, g_low, g_high = group
    return (low is None or low <= g_high) and (high is None or high >= g_low)


def window(when, day, now, preference):
    """The days the visitor is planning for ([] = any day)."""
    today = timezone.localdate(now)
    if day:
        return [day]
    if when == "today":
        return [today]
    if when == "tomorrow":
        return [today + timedelta(days=1)]
    if when == "weekend":
        return visitor_profile.days_off(now, preference)[:2]
    return []


def forecast_rows(lat, lon, days, forecasts):
    if lat is None or lon is None or not days:
        return []
    point = sunny.POINTS[sunny.nearest_point(float(lat), float(lon))]
    rows = []
    for d in days[:2]:
        raw = forecasts.get(point, {}).get(d.isoformat())
        text = weather.describe(raw)
        if text:
            rank = sunny.sun_rank(raw)
            rows.append({
                "day": weather.WEEKDAYS_JA[d.weekday()], "emoji": text["emoji"],
                "temp": text.get("temp", "").split(" ")[0], "rank": rank, "cls": WX_CLASS.get(rank[0], ""),
            })
    return rows


# ---------------------------------------------------------------------------
# Items: one shape for every kind
# ---------------------------------------------------------------------------

def event_items(now, days, f):
    start = end = None
    if days:
        tz = timezone.get_current_timezone()
        start = max(now, timezone.make_aware(datetime.combine(days[0], time.min), tz))
        end = timezone.make_aware(datetime.combine(days[-1] + timedelta(days=1), time.min), tz)
    items = []
    for event in live_events(now):
        dates = event.upcoming_dates
        if start is not None:
            dates = [o for o in dates if (o.end_at or o.start_at) > start and o.start_at < end]
        if not dates or not is_one_off(event):
            continue
        loc = event.location
        if f["family"] and not is_family(event):
            continue
        if f["free"] and not event.is_free:
            continue
        if f["rainy"] and not event.is_indoor:
            continue
        if f["easy"] and event.language_barrier not in ("none", "english", "japanese"):
            continue
        area = AREA_OF_CANTON.get(loc.canton, "") if loc else ""
        if f["areas"] and area not in f["areas"]:
            continue
        low, high = event_ages(event)
        if f["age"] and not ages_fit(low, high, f["age"]):
            continue
        relevance = 0
        if f["words"]:
            matched, relevance = text_search.score(text_search.event_document(event), f["words"])
            if matched < f["need"]:
                continue
        decorate_event(event, now)
        first = dates[0]
        lat = float(loc.latitude) if loc and loc.latitude is not None else None
        lon = float(loc.longitude) if loc and loc.longitude is not None else None
        items.append({
            "kind": "event", "kind_label": "イベント", "pk": event.pk, "title": event.title,
            "url": reverse("outings:event_detail", args=[event.pk]),
            "when": first.start_at, "when_label": schedule.occurrence_label(first, now),
            "sub": loc.city if loc else "", "emoji": event.display_emoji, "image": event.image_url,
            "desc": sunny.short_text(event.highlight_ja or event.summary_ja, 80),
            "badges": event.badges[:3],
            "lat": lat, "lon": lon, "area": area,
            # Events only happen on those days: one step up against places that are always there.
            "base": sunny.score_from_100(event.ai_score) + 1 + (0.5 if event.listing_tier == "featured" else 0),
            "rain_ok": event.is_indoor, "canton": loc.canton if loc else "",
            "new": event.created_at, "relevance": relevance,
        })
    return items


def trip_items(f):
    from .tourist_views import tourist_spot_queryset
    if f["family"] or f["free"] or f["rainy"]:
        return []  # trips don't know these; 子連れ shows the family places instead
    spots = tourist_spot_queryset()
    if not f["words"]:
        spots = spots.only(
            "pk", "title_ja", "title_original", "spot_type", "latitude", "longitude", "ai_quality_score",
            "details", "intro_ja", "summary_ja", "updated_at",
        )
    items = []
    for spot in spots:
        relevance = 0
        if f["words"]:
            document = text_search.trip_document(spot) + [(text_search.TEXT, text_search.normalize(spot.intro_ja))]
            matched, relevance = text_search.score(document, f["words"])
            if matched < f["need"]:
                continue
        area = area_of_point(spot.latitude, spot.longitude)
        if f["areas"] and area not in f["areas"]:
            continue
        photo = (spot.details or {}).get("approved_image") or {}
        items.append({
            "kind": "trip", "kind_label": spot.get_spot_type_display(), "pk": spot.pk,
            "title": (spot.title_ja or spot.title_original).split("｜")[0],
            "url": reverse("outings:tourist_spot_detail", args=[spot.pk]), "when": None,
            "sub": dict((k, l) for k, l, _ in AREAS).get(area, ""),
            "emoji": sunny.SPOT_TYPE_EMOJI.get(spot.spot_type, "📍"), "image": photo.get("url", ""),
            "desc": sunny.short_text(spot.intro_ja or spot.summary_ja, 80), "badges": [],
            "lat": spot.latitude, "lon": spot.longitude, "area": area,
            "base": sunny.score_from_100(spot.ai_quality_score), "rain_ok": False, "canton": "",
            "new": spot.updated_at, "relevance": relevance,
        })
    return items


def kids_items(f, month):
    spots = published_spots()
    if f["free"]:
        spots = spots.exclude(price=FamilySpot.Price.PAID)
    if f["rainy"]:
        spots = spots.filter(rainy_ok=True)
    if f["easy"]:
        spots = spots.filter(language__in=["none", "little"])
    if f["kind"]:
        spots = spots.filter(kind=f["kind"])
    if f["trip"] == "day":
        spots = spots.exclude(trip=FamilySpot.Trip.OVERNIGHT)
    elif f["trip"] == "overnight":
        spots = spots.exclude(trip=FamilySpot.Trip.DAY)
    items, lookups = [], 0
    for spot in spots:
        if not spot.open_in(month):
            continue
        area = AREA_OF_CANTON.get(spot.canton, "")
        if f["areas"] and area not in f["areas"]:
            continue
        if f["age"] and not ages_fit(spot.age_min, spot.age_max, f["age"]):
            continue
        relevance = 0
        if f["words"]:
            document = [
                (text_search.TITLE, text_search.normalize(f"{spot.name} {spot.name_ja}")),
                (text_search.PLACE, text_search.normalize(f"{spot.town} {spot.area_label if hasattr(spot, 'area_label') else ''}")),
                (text_search.GENRE, text_search.normalize(spot.get_kind_display())),
                (text_search.TEXT, text_search.normalize(f"{spot.summary_ja} {spot.intro_ja} {spot.tips_ja}")),
            ]
            matched, relevance = text_search.score(document, f["words"])
            if matched < f["need"]:
                continue
        if spot.latitude is None and lookups < sunny.MAX_LOOKUPS:
            lookups += 1
            sunny.locate(spot)
        decorate_spot(spot)
        items.append({
            "kind": "kids", "kind_label": spot.get_kind_display(), "pk": spot.pk, "title": spot.title,
            "url": reverse("outings:spot_detail", args=[spot.pk]), "when": None,
            "sub": spot.town or spot.area_label, "emoji": spot.emoji, "image": spot.image_url,
            "desc": sunny.short_text(spot.summary_ja or spot.intro_ja, 80), "badges": spot.badges[:3],
            "lat": spot.latitude, "lon": spot.longitude, "area": area,
            "base": spot.recommend, "rain_ok": spot.rainy_ok, "canton": spot.canton, "ages": (spot.age_min, spot.age_max),
            "new": spot.updated_at, "relevance": relevance,
        })
    return items


VISIT_TARGET = {"event": OutingsVisit.Target.EVENT, "trip": OutingsVisit.Target.TRIP, "kids": OutingsVisit.Target.KIDS}


def score_items(items, days, forecasts, preference):
    member = {}
    for kind, target in VISIT_TARGET.items():
        ids = [i["pk"] for i in items if i["kind"] == kind]
        if ids:
            member.update({(kind, pk): v for pk, v in ratings(target, ids).items()})
    cantons = visitor_profile.area_cantons(preference)
    for item in items:
        item["wx"] = forecast_rows(item["lat"], item["lon"], days, forecasts)
        best = min((r["rank"] for r in item["wx"]), default=(9, 100))
        item["wx_rank"] = best
        avg, count = member.get((item["kind"], item["pk"]), (None, 0))
        base = avg if count >= MEMBER_RATINGS_NEEDED else item["base"]
        item["score"] = sunny.recommend(base, best, item["rain_ok"])
        item["stars"] = stars_text(item["score"])
        item["member_avg"] = round(avg, 1) if avg else None
        item["member_count"] = count
        # The visitor's own areas a little higher (only for ordering).
        item["order"] = item["score"] + (0.5 if (item["canton"] in cantons or item["area"] in (preference.areas if preference else [])) else 0)


def sort_items(items, sort):
    if sort == "sunny":
        items.sort(key=lambda i: (min(i["wx_rank"][0], 1) if i["rain_ok"] and i["wx_rank"][0] < 9 else i["wx_rank"][0], -i["order"], i["title"]))
    elif sort == "date":
        far = timezone.now() + timedelta(days=3650)
        items.sort(key=lambda i: (i["when"] or far, -i["order"], i["title"]))
    else:
        # With a keyword: better text matches first, then おすすめ.
        items.sort(key=lambda i: (-i.get("relevance", 0), -i["order"], i["when"] or timezone.now() + timedelta(days=3650), i["title"]))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

# Conditions remembered between visits (子連れ has its own cookie; type and keyword are not kept).
REMEMBER = ("when", "day", "area", "age", "free", "rainy", "easy", "sort")
REMEMBER_COOKIE = "outings_find"


def effective_query(request):
    """(query, save): the request's conditions, or the last ones used when none are given."""
    from django.http import QueryDict
    get = request.GET
    if get.get("reset") == "1":
        return QueryDict(mutable=True), "clear"
    if any(key in get for key in REMEMBER):
        return get, "save"
    saved = request.COOKIES.get(REMEMBER_COOKIE, "")
    if not saved:
        return get, ""
    query = get.copy()
    for key, values in QueryDict(saved).lists():
        if key in REMEMBER:
            query.setlist(key, values)
    return query, ""


def read_filters(request, now, preference, get=None):
    get = request.GET if get is None else get
    kind = get.get("type", "all")
    if kind not in dict(TYPES):
        kind = "all"
    # A keyword search looks at every day unless a day is chosen.
    when = get.get("when", "any" if get.get("q") else "weekend")
    if when not in dict(WHEN):
        when = "weekend"
    day = None
    days = sunny.days_to_pick(now)
    for option, _ in days:
        if option.isoformat() == get.get("day"):
            day = option
    family, family_explicit = kids_choice(request, "family")
    areas = [a for a in get.getlist("area") if a in AREA_CENTRES]
    age = next((g for g in AGE_GROUPS if g[0] == get.get("age")), None)
    sort = get.get("sort", "")
    if sort not in dict(SORTS):
        sort = "sunny" if (day or when != "any") else "recommended"
    return {
        "type": kind, "when": when, "day": day, "days": days, "family": family,
        "family_explicit": family_explicit, "areas": areas, "age": age,
        "free": get.get("free") == "1", "rainy": get.get("rainy") == "1", "easy": get.get("easy") == "1",
        "q": get.get("q", "").strip()[:100], "sort": sort,
        # Only from HOME links: kind of 子連れスポット, day trip or overnight.
        "kind": get.get("kind") if get.get("kind") in FamilySpot.Kind.values else "",
        "trip": get.get("trip") if get.get("trip") in ("day", "overnight") else "",
    }


def collect(f, now, days, month):
    found = {"event": [], "trip": [], "kids": []}
    if f["type"] in ("all", "event"):
        found["event"] = event_items(now, days, f)
    if f["type"] in ("all", "trip"):
        found["trip"] = trip_items(f)
    if f["type"] in ("all", "kids") or (f["type"] == "trip" and f["family"]):
        found["kids"] = kids_items(f, month)
    return found


def find(request):
    from .map_points import wants_map
    now = timezone.now()
    visitor_id = get_visitor_id(request)
    preference = visitor_profile.get_profile(visitor_id)
    query, remember = effective_query(request)
    f = read_filters(request, now, preference, query)
    f["words"] = text_search.tokens(f["q"])
    f["need"] = len(f["words"])
    if f["q"] and not query.get("sort"):
        f["sort"] = "recommended"  # keyword: best matches first
    days = window(f["when"], f["day"], now, preference)
    month = (days[0] if days else timezone.localdate(now)).month

    found = collect(f, now, days, month)
    f["partial"] = False
    if f["need"] > 1 and not any(found.values()):
        # Nothing has every word: show what has at least one.
        f["need"] = 1
        found = collect(f, now, days, month)
        f["partial"] = any(found.values())
    items = found["event"] + found["trip"] + found["kids"]
    forecasts = weather._forecasts(sunny.POINTS) if days else {}
    score_items(items, days, forecasts, preference)
    sort_items(items, f["sort"])

    if wants_map(request):
        from django.http import JsonResponse
        points = [
            {"title": i["title"], "url": i["url"], "lat": round(float(i["lat"]), 5), "lon": round(float(i["lon"]), 5),
             "emoji": i["emoji"], "sub": i["sub"], "wx": i["wx"][0]["emoji"] if i["wx"] else "",
             "cls": i["wx"][0]["cls"] if i["wx"] else ""}
            for i in items if i["lat"] is not None and i["lon"] is not None
        ]
        return JsonResponse({"points": points[:MAX_POINTS], "total": len(items), "shown": min(len(points), MAX_POINTS)})

    page_obj = Paginator(items, PAGE_SIZE).get_page(request.GET.get("page"))

    params = query.copy()
    for key in ("page", "reset", "map"):
        params.pop(key, None)

    def qs(**changes):
        p = params.copy()
        for key, value in changes.items():
            if value in ("", None):
                p.pop(key, None)
            else:
                p[key] = value
        return p.urlencode()

    more = params.copy()
    if page_obj.has_next():
        more["page"] = page_obj.next_page_number()
    sunny_areas = []
    if days:
        points = sunny.point_forecasts(days[0])
        sunny_areas = [p["name"] for p in sorted((p for p in points if p["sunny"]), key=lambda p: p["rank"])][:6]

    counts = {"event": len(found["event"]), "trip": len(found["trip"]), "kids": len(found["kids"])}
    bits = []
    if f["day"]:
        bits.append(next(label for d, label in f["days"] if d == f["day"]))
    else:
        bits.append(dict(WHEN)[f["when"]])
    if f["family"]:
        bits.append("子連れ" + (f"（{f['age'][1]}）" if f["age"] else ""))
    bits += [label for key, label, _ in AREAS if key in f["areas"]]
    bits += [label for key, label in CONDITIONS if f[key]]
    if f["q"]:
        bits.append(f"「{f['q']}」")
    is_filtered = bool(f["areas"] or f["age"] or f["free"] or f["rainy"] or f["easy"] or f["q"] or f["day"] or f["when"] != "weekend")
    response = render(request, "outings/find.html", {
        "f": f,
        "items": page_obj.object_list,
        "page_obj": page_obj,
        "more_qs": more.urlencode(),
        "count": len(items),
        "types": [{"key": k, "label": l, "active": k == f["type"], "qs": qs(type="" if k == "all" else k),
                   "count": len(items) if k == "all" else counts.get(k, 0)} for k, l in TYPES],
        "whens": [{"key": k, "label": l, "active": not f["day"] and k == f["when"]} for k, l in WHEN],
        "day_options": [{"value": d.isoformat(), "label": label, "active": d == f["day"]} for d, label in f["days"]],
        "areas": [{"key": k, "label": l, "active": k in f["areas"]} for k, l, _ in AREAS],
        "ages": [{"key": g[0], "label": g[1], "active": f["age"] == g} for g in AGE_GROUPS],
        "conditions": [{"key": k, "label": l, "active": f[k]} for k, l in CONDITIONS],
        "sorts": [{"key": k, "label": l, "active": k == f["sort"], "qs": qs(sort=k)} for k, l in SORTS],
        "days": days,
        "days_label": "・".join(f"{d.month}/{d.day}（{weather.WEEKDAYS_JA[d.weekday()]}）" for d in days),
        "sunny_areas": sunny_areas,
        "has_forecast": bool(forecasts),
        "is_filtered": is_filtered,
        "summary_bits": bits,
        "trips_hidden": f["type"] in ("all", "trip") and (f["family"] or f["free"] or f["rainy"]),
    })
    if f["family_explicit"]:
        remember_kids(response, f["family"])
    if remember == "save":
        from django.http import QueryDict
        kept = QueryDict(mutable=True)
        for key in REMEMBER:
            if key in query and key != "day":
                kept.setlist(key, query.getlist(key))
        response.set_cookie(REMEMBER_COOKIE, kept.urlencode(), max_age=180 * 24 * 3600, samesite="Lax")
    elif remember == "clear":
        response.delete_cookie(REMEMBER_COOKIE)
    return set_visitor_cookie(request, response, visitor_id)


# ---------------------------------------------------------------------------
# Old list URLs: keep links and bookmarks working
# ---------------------------------------------------------------------------

def _go(params):
    from django.http import HttpResponseRedirect
    from django.http import QueryDict
    query = QueryDict(mutable=True)
    for key, value in params.items():
        if isinstance(value, list):
            for v in value:
                if v:
                    query.appendlist(key, v)
        elif value not in ("", None):
            query[key] = value
    url = reverse("outings:find")
    return HttpResponseRedirect(url + ("?" + query.urlencode() if query else ""))


def _when(value):
    return {"today": "today", "tomorrow": "tomorrow", "weekend": "weekend"}.get(value, "any" if value else "")


def _areas_from_regions(values):
    return sorted({AREA_OF_CANTON.get(v.upper(), "") for v in values if v and v != "all"} - {""})


def from_events(request):
    g = request.GET
    return _go({
        "type": "event", "when": _when(g.get("when", "")), "area": _areas_from_regions(g.getlist("region")),
        "family": g.get("family", ""), "easy": g.get("easy", ""), "free": g.get("free", ""),
    })


def from_trips(request):
    g = request.GET
    kids = g.get("kids") == "1"
    return _go({
        "type": "kids" if kids else "trip", "family": "1" if kids else g.get("kids", ""),
        "area": [g.get("area", "")] if g.get("area") in AREA_CENTRES else [], "age": g.get("age", ""),
        "rainy": g.get("rainy", ""), "easy": g.get("easy", ""), "free": g.get("free", ""), "q": g.get("q", ""),
        "kind": g.get("kind", ""), "trip": g.get("trip", ""),
    })


def from_sunny(request):
    g = request.GET
    what = {"kids": "kids", "trips": "trip", "events": "event"}.get(g.get("what", ""), "")
    return _go({
        "type": what, "family": "1" if what == "kids" else "", "day": g.get("day", ""),
        "rainy": g.get("rainy", ""), "sort": "sunny",
    })


def from_search(request):
    g = request.GET
    return _go({
        "type": "" if g.get("q") else "event",
        "q": g.get("q", ""), "when": _when(g.get("when", "")) or "any", "area": _areas_from_regions(g.getlist("region")),
        "family": "1" if g.get("tag") == "family" else g.get("family", ""), "free": g.get("free", ""),
        "sort": "sunny" if g.get("sort") == "sunny" else ("date" if g.get("sort") == "date" else ""),
    })


# ---------------------------------------------------------------------------
# HOME: picks for this visitor, from the same items as さがす
# ---------------------------------------------------------------------------

def base_filters(family, **changes):
    f = {
        "type": "all", "when": "weekend", "day": None, "days": [], "family": family, "family_explicit": False,
        "areas": [], "age": None, "free": False, "rainy": False, "easy": False, "q": "", "words": [], "need": 0,
        "sort": "sunny", "kind": "", "trip": "", "partial": False,
    }
    f.update(changes)
    return f


def sunny_area_names(days):
    names = []
    for day in days[:2]:
        for point in sorted((p for p in sunny.point_forecasts(day) if p["sunny"]), key=lambda p: p["rank"]):
            if point["name"] not in names:
                names.append(point["name"])
    return names


def home_picks(preference, now, days, limit=8):
    """(picks, events, overnight, mode): mode is 'sunny' (show sunny places first),
    'rainy' (rain everywhere: places that work in the rain) or '' (no forecast)."""
    family = visitor_profile.wants_kids(preference) is not False
    age = None
    ages = visitor_profile.age_range(preference)
    month = (days[0] if days else timezone.localdate(now)).month
    forecasts = weather._forecasts(sunny.POINTS) if days else {}

    f = base_filters(family, trip="day", age=age)
    found = collect(f, now, days, month)
    items = found["event"] + found["trip"] + found["kids"]
    if ages and family:
        group = ("", "", ages[0], ages[1])
        items = [i for i in items if i["kind"] != "kids" or ages_fit(*i["ages"], group)]
    score_items(items, days, forecasts, preference)
    # A different order among equals each week, the same all week long.
    import random
    week = timezone.localdate(now).isocalendar()
    random.Random(f"{week[0]}-{week[1]}").shuffle(items)

    mode = ""
    if forecasts:
        sunny_somewhere = any(i["wx"] and i["wx_rank"][0] <= 1 for i in items)
        if sunny_somewhere:
            mode = "sunny"
            sort_items(items, "sunny")
        else:
            mode = "rainy"
            dry = [i for i in items if i["rain_ok"]]
            items = dry or items
            sort_items(items, "recommended")
    else:
        sort_items(items, "recommended")

    # A mix: no more than half events, so places and events both show.
    picks, events_taken = [], 0
    for item in items:
        if item["kind"] == "event":
            if events_taken >= limit // 2:
                continue
            events_taken += 1
        picks.append(item)
        if len(picks) == limit:
            break

    events = [i for i in items if i["kind"] == "event" and i not in picks][:6]
    over = collect(base_filters(family, type="kids", trip="overnight"), now, days, month)["kids"]
    score_items(over, days, forecasts, preference)
    sort_items(over, "sunny" if mode == "sunny" else "recommended")
    return picks, events, over[:6], mode

