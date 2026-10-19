"""Event listing, search, detail, calendar export and hearts."""

from datetime import datetime, time, timedelta
from urllib.parse import quote_plus, urlencode

from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .cards import decorate
from .forms import OutingsCommentForm
from .models import (
    Event,
    EventCategory,
    EventHeart,
    EventOccurrence,
    OutingsComment,
    OutingsPreference,
)
from .regions import REGION_CHOICES, REGION_NAMES, clean_region, clean_regions, search_variants
from .services import schedule, weather
from .visitor import get_visitor_id, set_visitor_cookie


PERIODS = [
    ("all", "すべて"),
    ("today", "今日"),
    ("tomorrow", "明日"),
    ("weekend", "今週末"),
    ("week", "7日以内"),
    ("month", "30日以内"),
]

TIER_ORDER = {
    Event.ListingTier.FEATURED: 0,
    Event.ListingTier.STANDARD: 1,
    Event.ListingTier.COMMUNITY: 1,
    Event.ListingTier.COMPACT: 2,
}

PAGE_SIZE = 40
FEATURED_LIMIT = 6


# =========================================================
# Helpers
# =========================================================

def _visible_statuses(request):
    statuses = [Event.Status.PUBLISHED]
    if request.user.is_authenticated and request.user.is_staff and request.GET.get("preview") == "1":
        statuses.append(Event.Status.DRAFT)
    return statuses


def live_occurrences(now):
    return (
        EventOccurrence.objects
        .filter(is_cancelled=False)
        .filter(Q(end_at__gt=now) | Q(end_at__isnull=True, start_at__gte=now))
        .order_by("start_at")
    )


def live_events(now, statuses=(Event.Status.PUBLISHED,)):
    """Events with at least one occurrence that is neither cancelled nor over."""
    return (
        Event.objects
        .filter(
            status__in=statuses,
            pk__in=live_occurrences(now).values("event_id"),
        )
        .select_related("category", "location")
        .prefetch_related(
            "tags",
            Prefetch("occurrences", queryset=live_occurrences(now), to_attr="upcoming_dates"),
        )
    )


def period_range(period, now):
    """(start, end) of a period in aware datetimes; end None means open."""
    today = timezone.localdate(now)
    tz = timezone.get_current_timezone()

    def midnight(day):
        return timezone.make_aware(datetime.combine(day, time.min), tz)

    if period == "today":
        return now, midnight(today + timedelta(days=1))
    if period == "tomorrow":
        return midnight(today + timedelta(days=1)), midnight(today + timedelta(days=2))
    if period == "weekend":
        # On Sunday "this weekend" is today; Saturday and Sunday otherwise.
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        if today.weekday() == 6:
            saturday = today - timedelta(days=1)
        return max(now, midnight(saturday)), midnight(saturday + timedelta(days=2))
    if period == "week":
        return now, midnight(today + timedelta(days=8))
    if period == "month":
        return now, midnight(today + timedelta(days=31))
    return now, None


def first_in_range(dates, start, end):
    for o in dates:
        o_end = o.end_at or o.start_at
        if o_end > start and (end is None or o.start_at < end):
            return o
    return None


def hearted_ids_for(visitor_id, events):
    return set(
        EventHeart.objects.filter(visitor_id=visitor_id, event_id__in=[e.pk for e in events])
        .values_list("event_id", flat=True)
    )


def querystring(params, **changes):
    merged = {**params, **changes}
    pairs = []
    for key, value in merged.items():
        if value in (None, "", False):
            continue
        if isinstance(value, (list, tuple)):
            pairs += [(key, v) for v in value]
        else:
            pairs.append((key, value))
    return urlencode(pairs)


def _preference(visitor_id):
    return OutingsPreference.objects.filter(visitor_id=visitor_id).first()


# =========================================================
# Event list
# =========================================================

def event_home(request):
    now = timezone.now()
    visitor_id = get_visitor_id(request)
    statuses = _visible_statuses(request)

    period = request.GET.get("when", "all")
    if period not in dict(PERIODS):
        period = "all"
    category_slug = request.GET.get("category", "").strip()
    family = request.GET.get("family") == "1"
    no_language = request.GET.get("easy") == "1"
    free = request.GET.get("free") == "1"

    # Regions: explicit choice, "all", or the visitor's favourite regions.
    preference = _preference(visitor_id)
    favorites = clean_regions(preference.favorite_regions if preference and preference.personalization_enabled else [])
    raw_regions = request.GET.getlist("region")
    using_favorites = False
    if raw_regions == ["all"]:
        regions = []
    elif raw_regions:
        regions = clean_regions(raw_regions)
    else:
        regions = favorites
        using_favorites = bool(favorites)

    events = list(live_events(now, statuses))
    win_start, win_end = period_range(period, now)

    def matches(event, *, skip_region=False):
        if not skip_region and regions and not (event.location and event.location.canton in regions):
            return False
        if category_slug and not (event.category and event.category.slug == category_slug):
            return False
        tags = {t.slug for t in event.tags.all()}
        if family and not tags & {"family", "children", "baby"}:
            return False
        if no_language and event.language_barrier not in ("none", "english", "japanese"):
            return False
        if free and not event.is_free:
            return False
        return first_in_range(event.upcoming_dates, win_start, win_end) is not None

    region_counts = {}
    for event in events:
        if event.location and matches(event, skip_region=True):
            region_counts[event.location.canton] = region_counts.get(event.location.canton, 0) + 1

    matched = [e for e in events if matches(e)]
    hearted = hearted_ids_for(visitor_id, matched)
    for event in matched:
        decorate(event, now, hearted)
        event.list_occurrence = first_in_range(event.upcoming_dates, win_start, win_end)

    # Runs that are already open (exhibitions) would sit on "today" forever:
    # list them in their own section instead of the day groups.
    ongoing = [e for e in matched if e.is_long and e.list_occurrence.start_at < max(now, win_start)]
    ongoing_ids = {e.pk for e in ongoing}
    dated = [e for e in matched if e.pk not in ongoing_ids]

    def list_day(event):
        return timezone.localtime(max(event.list_occurrence.start_at, win_start)).date()

    dated.sort(key=lambda e: (
        list_day(e),
        TIER_ORDER.get(e.listing_tier, 1),
        -(e.ai_score or 0),
        e.list_occurrence.start_at,
    ))
    ongoing.sort(key=lambda e: (-(e.ai_score or 0), e.list_occurrence.end_at or e.list_occurrence.start_at))

    is_filtered = bool(regions or category_slug or family or no_language or free or period != "all")
    featured = []
    if not is_filtered or using_favorites:
        soon = now + timedelta(days=14)
        featured = sorted(
            (e for e in dated if e.listing_tier == Event.ListingTier.FEATURED and e.list_occurrence.start_at < soon),
            key=lambda e: e.list_occurrence.start_at,
        )[:FEATURED_LIMIT]

    if featured:
        featured_ids = {e.pk for e in featured}
        dated = [e for e in dated if e.pk not in featured_ids]

    page_obj = Paginator(dated, PAGE_SIZE).get_page(request.GET.get("page"))
    day_groups = []
    for event in page_obj.object_list:
        day = list_day(event)
        if not day_groups or day_groups[-1]["day"] != day:
            day_groups.append({"day": day, "label": _day_heading(day, now), "events": []})
        day_groups[-1]["events"].append(event)

    params = {
        "when": "" if period == "all" else period,
        "region": regions if raw_regions else [],
        "category": category_slug,
        "family": "1" if family else "",
        "easy": "1" if no_language else "",
        "free": "1" if free else "",
    }
    categories = sorted(
        {e.category.pk: e.category for e in events if e.category and e.category.is_active}.values(),
        key=lambda c: (c.sort_order, c.name),
    )
    response = render(request, "outings/event_home.html", {
        "periods": PERIODS,
        "period": period,
        "active_regions": regions,
        "using_favorites": using_favorites,
        "favorite_names": [REGION_NAMES.get(c, c) for c in favorites],
        "categories": categories,
        "active_category": category_slug,
        "family": family,
        "easy": no_language,
        "free": free,
        "is_filtered": is_filtered,
        "featured_events": featured,
        "day_groups": day_groups,
        "ongoing_events": ongoing if page_obj.number == 1 else [],
        "page_obj": page_obj,
        "result_count": len(dated) + len(ongoing) + len(featured),
        "page_qs_prev": querystring(params, page=page_obj.previous_page_number()) if page_obj.has_previous() else "",
        "page_qs_next": querystring(params, page=page_obj.next_page_number()) if page_obj.has_next() else "",
        "chips": _chips(params, period, regions, region_counts, family, no_language, free, category_slug, categories),
        "clear_qs": querystring({}, region=["all"]),
        "preview_mode": Event.Status.DRAFT in statuses,
    })
    return set_visitor_cookie(request, response, visitor_id)


def _day_heading(day, now):
    today = timezone.localdate(now)
    weekday = schedule.WEEKDAYS_JA[day.weekday()]
    label = f"{day.month}月{day.day}日（{weekday}）"
    if day == today:
        return f"今日・{label}"
    if day == today + timedelta(days=1):
        return f"明日・{label}"
    return label


def _chips(params, period, regions, region_counts, family, easy, free, category, categories):
    """Every filter chip with its label, state and link, so templates stay simple."""
    chips = {
        "periods": [
            {"label": label, "active": key == period, "qs": querystring(params, when="" if key == "all" else key, page="")}
            for key, label in PERIODS
        ],
        "regions": [{"label": "すべての地域", "active": not regions, "qs": querystring(params, region=["all"], page="")}],
        "toggles": [
            {"label": "家族向け", "icon": "bi-people", "active": family, "qs": querystring(params, family="" if family else "1", page="")},
            {"label": "言葉の壁が低い", "icon": "bi-translate", "active": easy, "qs": querystring(params, easy="" if easy else "1", page="")},
            {"label": "無料", "icon": "bi-cash-coin", "active": free, "qs": querystring(params, free="" if free else "1", page="")},
        ],
        "categories": [{"label": "すべて", "active": not category, "qs": querystring(params, category="", page="")}],
    }
    for code, name in REGION_CHOICES:
        count = region_counts.get(code, 0)
        if not count and code not in regions:
            continue
        chosen = [c for c in regions if c != code] if code in regions else regions + [code]
        chips["regions"].append({
            "label": name, "count": count, "active": code in regions,
            "qs": querystring(params, region=chosen or ["all"], page=""),
        })
    for c in categories:
        chips["categories"].append({
            "label": c.name, "active": c.slug == category,
            "qs": querystring(params, category="" if c.slug == category else c.slug, page=""),
        })
    return chips


# =========================================================
# Search
# =========================================================

def search(request):
    now = timezone.now()
    statuses = _visible_statuses(request)
    region = clean_region(request.GET.get("region"))
    categories = EventCategory.objects.filter(is_active=True).order_by("sort_order", "name")
    category = request.GET.get("category", "").strip()
    if category not in set(categories.values_list("slug", flat=True)):
        category = ""
    family_only = request.GET.get("tag") == "family"
    query = request.GET.get("q", "").strip()[:100]

    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    start_date = parse_date(date_from) if date_from else None
    end_date = parse_date(date_to) if date_to else None
    if start_date is None:
        date_from = ""
    if end_date is None:
        date_to = ""
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date
        date_from, date_to = start_date.isoformat(), end_date.isoformat()
    tz = timezone.get_current_timezone()
    range_start = timezone.make_aware(datetime.combine(start_date, time.min), tz) if start_date else now
    range_end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), tz) if end_date else None

    events = live_events(now, statuses)
    if region:
        events = events.filter(location__canton=region)
    if category:
        events = events.filter(category__slug=category)
    if family_only:
        events = events.filter(tags__slug__in=["family", "children", "baby"])
    if query:
        text = Q()
        for variant in search_variants(query):
            text |= (
                Q(title__icontains=variant)
                | Q(title_original__icontains=variant)
                | Q(summary_ja__icontains=variant)
                | Q(highlight_ja__icontains=variant)
                | Q(location__city__icontains=variant)
                | Q(location__name__icontains=variant)
                | Q(category__name__icontains=variant)
            )
        events = events.filter(text)

    results = []
    for event in events.distinct():
        occurrence = first_in_range(event.upcoming_dates, max(now, range_start), range_end)
        if occurrence is None:
            continue
        event.list_occurrence = occurrence
        results.append(event)
    results.sort(key=lambda e: (e.list_occurrence.start_at, e.pk))

    page_obj = Paginator(results, 20).get_page(request.GET.get("page", 1))
    visitor_id = get_visitor_id(request)
    hearted = hearted_ids_for(visitor_id, page_obj.object_list)
    for event in page_obj.object_list:
        decorate(event, now, hearted)
        event.date_label = schedule.occurrence_label(event.list_occurrence, now)

    params = {
        "q": query, "region": region, "category": category,
        "tag": "family" if family_only else "", "date_from": date_from, "date_to": date_to,
        "preview": "1" if Event.Status.DRAFT in statuses else "",
    }
    response = render(request, "outings/search.html", {
        "events": page_obj.object_list,
        "page_obj": page_obj,
        "result_count": len(results),
        "regions": REGION_CHOICES,
        "active_region": region,
        "categories": categories,
        "active_category": category,
        "family_only": family_only,
        "query": query,
        "preview_mode": Event.Status.DRAFT in statuses,
        "date_from": date_from,
        "date_to": date_to,
        "page_qs_prev": querystring(params, page=page_obj.previous_page_number()) if page_obj.has_previous() else "",
        "page_qs_next": querystring(params, page=page_obj.next_page_number()) if page_obj.has_next() else "",
    })
    return set_visitor_cookie(request, response, visitor_id)


# =========================================================
# Detail
# =========================================================

def _visible_event(request, pk):
    if request.user.is_authenticated and request.user.is_staff:
        visibility = Q(status__in=[Event.Status.PUBLISHED, Event.Status.DRAFT])
    elif request.user.is_authenticated:
        visibility = Q(status=Event.Status.PUBLISHED) | Q(created_by=request.user, source__isnull=True)
    else:
        visibility = Q(status=Event.Status.PUBLISHED)
    return get_object_or_404(
        Event.objects.select_related("category", "location", "source")
        .prefetch_related("tags", "occurrences")
        .filter(visibility),
        pk=pk,
    )


def map_url(event):
    if not event.location:
        return ""
    place = " ".join(p for p in (event.location.name, event.location.address, event.location.city) if p)
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(place)


def event_detail(request, pk):
    event = _visible_event(request, pk)
    now = timezone.now()
    visitor_id = get_visitor_id(request)
    all_dates = list(event.occurrences.all())
    upcoming = schedule.upcoming(all_dates, now)
    cancelled = [o for o in all_dates if o.is_cancelled and o.start_at >= now]
    event.upcoming_dates = upcoming
    decorate(event, now, hearted_ids_for(visitor_id, [event]))
    weather.attach([event], now)
    date_rows = [
        {"label": schedule.occurrence_label(o, now), "ongoing": schedule.is_ongoing(o, now), "cancelled": False, "start": o.start_at}
        for o in upcoming
    ] + [
        {"label": schedule.occurrence_label(o, now), "ongoing": False, "cancelled": True, "start": o.start_at}
        for o in cancelled
    ]
    date_rows.sort(key=lambda row: row["start"])

    comments = (
        OutingsComment.objects.filter(event=event, parent__isnull=True)
        .select_related("author")
        .prefetch_related(Prefetch(
            "replies",
            queryset=OutingsComment.objects.filter(parent__isnull=False).select_related("author").order_by("created_at", "pk"),
        ))
        .order_by("created_at", "pk")
    )
    if request.user.is_authenticated:
        for comment in comments:
            for item in [comment, *comment.replies.all()]:
                item.can_delete = (
                    request.user.pk in (item.author_id, event.created_by_id) or request.user.is_staff
                )
                item.can_edit = request.user.pk == item.author_id and not item.is_deleted

    response = render(request, "outings/event_detail.html", {
        "event": event,
        "is_hearted": event.is_hearted,
        "heart_count": EventHeart.objects.filter(event=event).count(),
        "date_rows": date_rows,
        "is_over": not upcoming,
        "map_url": map_url(event),
        "age_note": (event.ai_details or {}).get("age_note", ""),
        "booking": (event.ai_details or {}).get("booking", ""),
        "comments": comments,
        "comment_count": OutingsComment.objects.filter(event=event, is_deleted=False).count(),
        "comment_form": OutingsCommentForm(),
    })
    return set_visitor_cookie(request, response, visitor_id)


def event_calendar(request, pk):
    """Download the upcoming dates as an .ics file for phone calendars."""
    event = _visible_event(request, pk)
    now = timezone.now()
    upcoming = schedule.upcoming(event.occurrences.all(), now)[:50]
    if not upcoming:
        raise Http404("No upcoming dates")
    url = request.build_absolute_uri(reverse("outings:event_detail", args=[event.pk]))
    response = HttpResponse(schedule.build_ics(event, upcoming, url=url, now=now), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="yapp-outings-{event.pk}.ics"'
    return response


# =========================================================
# Hearts
# =========================================================

@require_POST
def toggle_heart(request, pk):
    visitor_id = get_visitor_id(request)
    existing = EventHeart.objects.filter(event_id=pk, visitor_id=visitor_id).first()
    if existing:
        # Removing works even after the event ended or was unpublished.
        event = existing.event
        existing.delete()
        hearted = False
    else:
        event = get_object_or_404(Event, pk=pk, status=Event.Status.PUBLISHED)
        EventHeart.objects.get_or_create(event=event, visitor_id=visitor_id)
        hearted = True

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        response = JsonResponse({"hearted": hearted, "count": EventHeart.objects.filter(event=event).count()})
        return set_visitor_cookie(request, response, visitor_id)

    next_url = request.POST.get("next", "").strip()
    if not (next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure())):
        next_url = reverse("outings:event_detail", args=[event.pk]) if event.status == Event.Status.PUBLISHED else reverse("outings:saved_all")
    return set_visitor_cookie(request, HttpResponseRedirect(next_url), visitor_id)
