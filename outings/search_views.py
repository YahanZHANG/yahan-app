"""Search page: keyword, date, region, genre and conditions in one place.

Filters are plain links (chips), so every state has its own URL and works
without JavaScript. With a keyword, results are ranked by relevance and
matching trips are listed above the events.
"""

from datetime import datetime, time, timedelta

from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .cards import CATEGORY_EMOJI, decorate
from .discovery_views import make_trip_card
from .event_views import (
    _visible_statuses,
    first_in_range,
    hearted_ids_for,
    live_events,
    period_range,
    querystring,
)
from .models import Event, EventCategory
from .regions import REGION_CHOICES, REGION_NAMES, clean_regions
from .services import schedule
from .services import search as text_search
from .tourist_views import tourist_spot_queryset
from .visitor import get_visitor_id, set_visitor_cookie


PERIODS = [
    ("", "いつでも"),
    ("today", "今日"),
    ("tomorrow", "明日"),
    ("weekend", "今週末"),
    ("next_weekend", "来週末"),
    ("week", "7日以内"),
]

TOGGLES = [
    ("family", "家族向け", "bi-people"),
    ("free", "無料", "bi-cash-coin"),
    ("easy", "言葉の壁が低い", "bi-translate"),
]

SUGGESTED_WORDS = ["コンサート", "マーケット", "子ども", "美術館", "ハイキング", "Zürich", "Basel", "Luzern"]

PAGE_SIZE = 20
TRIP_LIMIT = 4
EASY_LANGUAGES = ("none", "english", "japanese")


def _window(period, start_date, end_date, now):
    """Date window of the search, from a custom range or a named period."""
    tz = timezone.get_current_timezone()
    if start_date or end_date:
        start = timezone.make_aware(datetime.combine(start_date, time.min), tz) if start_date else now
        end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), tz) if end_date else None
        return max(now, start), end
    if period == "next_weekend":
        start, end = period_range("weekend", now)
        saturday = end - timedelta(days=2)
        return saturday + timedelta(days=7), end + timedelta(days=7)
    if period:
        return period_range(period, now)
    return now, None


def search(request):
    now = timezone.now()
    statuses = _visible_statuses(request)
    get = request.GET

    query = get.get("q", "").strip()[:100]
    period = get.get("when", "")
    if period not in dict(PERIODS):
        period = ""
    date_from, date_to = get.get("date_from", "").strip(), get.get("date_to", "").strip()
    start_date = parse_date(date_from) if date_from else None
    end_date = parse_date(date_to) if date_to else None
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date
    date_from = start_date.isoformat() if start_date else ""
    date_to = end_date.isoformat() if end_date else ""
    if date_from or date_to:
        period = ""
    regions = clean_regions(get.getlist("region"))
    category_choices = list(EventCategory.objects.filter(is_active=True).order_by("sort_order", "name"))
    category = get.get("category", "").strip()
    if category not in {c.slug for c in category_choices}:
        category = ""
    flags = {
        "family": get.get("family") == "1" or get.get("tag") == "family",
        "free": get.get("free") == "1",
        "easy": get.get("easy") == "1",
    }
    sort = get.get("sort", "")
    if sort not in ("", "date"):
        sort = ""

    params = {
        "q": query, "when": period, "date_from": date_from, "date_to": date_to,
        "region": regions, "category": category,
        "family": "1" if flags["family"] else "", "free": "1" if flags["free"] else "",
        "easy": "1" if flags["easy"] else "", "sort": sort,
        "preview": "1" if Event.Status.DRAFT in statuses else "",
    }
    words = text_search.tokens(query)

    # ------------------------------------------------------------------
    # Match every live event once; the same matcher counts what dropping a
    # condition would add, for the "no results" suggestions.
    # ------------------------------------------------------------------
    events = list(live_events(now, statuses))
    documents = {e.pk: text_search.event_document(e) for e in events} if words else {}

    def matches(event, state):
        location = event.location
        if state["regions"] and not (location and location.canton in state["regions"]):
            return None
        if state["category"] and not (event.category_id and event.category.slug == state["category"]):
            return None
        if state["family"] and not {t.slug for t in event.tags.all()} & text_search.FAMILY_TAGS:
            return None
        if state["free"] and not event.is_free:
            return None
        if state["easy"] and event.language_barrier not in EASY_LANGUAGES:
            return None
        start, end = state["window"]
        occurrence = first_in_range(event.upcoming_dates, start, end)
        if occurrence is None:
            return None
        if state["words"]:
            matched, relevance = text_search.score(documents[event.pk], state["words"])
            if matched < state["need"]:
                return None
        else:
            matched, relevance = 0, 0
        return occurrence, matched, relevance

    state = {
        "regions": regions, "category": category, **flags,
        "window": _window(period, start_date, end_date, now),
        "words": words, "need": len(words),
    }

    def run(state):
        found = []
        for event in events:
            hit = matches(event, state)
            if hit:
                found.append((event, *hit))
        return found

    found = run(state)
    partial = False
    if not found and len(words) > 1:
        # No event has every word: show those with at least one, best first.
        found = run({**state, "need": 1})
        partial = bool(found)

    if words and sort != "date":
        # More query words matched first, then where they matched, with a
        # small lift for well-rated and featured events.
        found.sort(key=lambda row: (
            -row[2],
            -(row[3] + (row[0].ai_score or 0) / 50 + (row[0].listing_tier == Event.ListingTier.FEATURED)),
            row[1].start_at,
        ))
    else:
        found.sort(key=lambda row: (row[1].start_at, row[0].pk))

    # Region counts for the chips, ignoring the region filter itself.
    region_counts = {}
    for event, *_ in run({**state, "regions": [], "need": 1 if partial else state["need"]}):
        if event.location:
            region_counts[event.location.canton] = region_counts.get(event.location.canton, 0) + 1

    # ------------------------------------------------------------------
    # Trips (only for a keyword search)
    # ------------------------------------------------------------------
    trip_cards = []
    if words and not regions and not category and not any(flags.values()):
        scored = []
        for spot in tourist_spot_queryset():
            matched, relevance = text_search.score(text_search.trip_document(spot), words)
            if matched == len(words):
                scored.append((relevance, spot.ai_quality_score or 0, spot))
        scored.sort(key=lambda row: (-row[0], -row[1], row[2].pk))
        trip_cards = [make_trip_card(spot) for _, _, spot in scored[:TRIP_LIMIT]]

    # ------------------------------------------------------------------
    # Page of event results
    # ------------------------------------------------------------------
    page_obj = Paginator(found, PAGE_SIZE).get_page(get.get("page", 1))
    visitor_id = get_visitor_id(request)
    page_events = [row[0] for row in page_obj.object_list]
    hearted = hearted_ids_for(visitor_id, page_events)
    for event, occurrence, *_ in page_obj.object_list:
        decorate(event, now, hearted)
        event.list_occurrence = occurrence
        event.date_label = schedule.occurrence_label(occurrence, now)

    # ------------------------------------------------------------------
    # Chips, active conditions and "no results" help
    # ------------------------------------------------------------------
    def link(**changes):
        return querystring(params, page="", **changes)

    has_dates = bool(date_from or date_to)
    chips = {
        "periods": [
            {"label": label, "active": key == period and not has_dates, "qs": link(when=key, date_from="", date_to="")}
            for key, label in PERIODS
        ],
        "regions": [{"label": "すべて", "active": not regions, "qs": link(region=[])}],
        "categories": [{"label": "すべて", "emoji": "✨", "active": not category, "qs": link(category="")}],
        "toggles": [
            {"label": label, "icon": icon, "active": flags[key], "qs": link(**{key: "" if flags[key] else "1"})}
            for key, label, icon in TOGGLES
        ],
    }
    for code, name in REGION_CHOICES:
        count = region_counts.get(code, 0)
        if not count and code not in regions:
            continue
        chosen = [c for c in regions if c != code] if code in regions else regions + [code]
        chips["regions"].append({"label": name, "count": count, "active": code in regions, "qs": link(region=chosen)})
    for c in category_choices:
        chips["categories"].append({
            "label": c.name, "emoji": CATEGORY_EMOJI.get(c.slug, "🎈"), "active": c.slug == category,
            "qs": link(category="" if c.slug == category else c.slug),
        })

    active = []
    if has_dates:
        label = f"{_short(start_date) if start_date else ''}〜{_short(end_date) if end_date else ''}"
        active.append({"label": label, "qs": link(date_from="", date_to=""), "drop": {"window": (now, None)}})
    elif period:
        active.append({"label": dict(PERIODS)[period], "qs": link(when=""), "drop": {"window": (now, None)}})
    for code in regions:
        active.append({"label": REGION_NAMES.get(code, code), "qs": link(region=[c for c in regions if c != code]),
                       "drop": {"regions": [c for c in regions if c != code]}})
    if category:
        name = next((c.name for c in category_choices if c.slug == category), category)
        active.append({"label": name, "qs": link(category=""), "drop": {"category": ""}})
    for key, label, _ in TOGGLES:
        if flags[key]:
            active.append({"label": label, "qs": link(**{key: ""}), "drop": {key: False}})

    relax = []
    if not found:
        for item in active:
            count = len(run({**state, "need": 1 if len(words) > 1 else len(words), **item["drop"]}))
            if count:
                relax.append({"label": item["label"], "count": count, "qs": item["qs"]})
        if words and (active or len(words) > 1):
            count = len(run({**state, "words": []}))
            if count:
                relax.append({"label": f"キーワード「{query}」", "count": count, "qs": link(q="")})
        relax.sort(key=lambda item: -item["count"])

    response = render(request, "outings/search.html", {
        "query": query,
        "events": page_events,
        "page_obj": page_obj,
        "result_count": len(found),
        "trip_cards": trip_cards,
        "partial": partial,
        "chips": chips,
        "active": active,
        "relax": relax[:3],
        "clear_qs": link(q=query, when="", date_from="", date_to="", region=[], category="", family="", free="", easy=""),
        "sort": sort,
        "sort_relevance_qs": link(sort=""),
        "sort_date_qs": link(sort="date"),
        # Hidden fields that keep the other conditions when a form is sent.
        "keyword_hidden": _hidden(params, "q", "page"),
        "date_hidden": _hidden(params, "when", "date_from", "date_to", "page"),
        "date_from": date_from,
        "date_to": date_to,
        "has_dates": has_dates,
        "filters_open": bool(regions or category or any(flags.values())),
        "suggested_words": SUGGESTED_WORDS,
        "preview_mode": Event.Status.DRAFT in statuses,
        "page_qs_prev": querystring(params, page=page_obj.previous_page_number()) if page_obj.has_previous() else "",
        "page_qs_next": querystring(params, page=page_obj.next_page_number()) if page_obj.has_next() else "",
    })
    return set_visitor_cookie(request, response, visitor_id)


def _hidden(params, *skip):
    pairs = []
    for key, value in params.items():
        if key in skip or not value:
            continue
        pairs += [(key, v) for v in value] if isinstance(value, list) else [(key, value)]
    return pairs


def _short(day):
    return f"{day.month}/{day.day}"
