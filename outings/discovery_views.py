
from django.templatetags.static import static

from django.db.models import (
    Q,
    Min,
    Prefetch,
)

from django.shortcuts import render

from django.utils import timezone

from .models import (
    Event,
    EventHeart,
    EventOccurrence,
    TouristSpot,
    TouristSpotHeart,
)

from .visitor import (
    get_visitor_id,
    set_visitor_cookie,
)


# =========================================================
# Available events
# =========================================================

def available_events():

    now = timezone.now()

    valid_dates = (
        EventOccurrence.objects
        .filter(
            is_cancelled=False,
        )
        .filter(
            Q(end_at__gt=now)
            | Q(
                end_at__isnull=True,
                start_at__gte=now,
            )
        )
        .order_by("start_at")
    )

    return (
        Event.objects
        .filter(
            status=Event.Status.PUBLISHED,
        )
        .filter(
            Q(
                occurrences__end_at__gt=now,
                occurrences__is_cancelled=False,
            )
            | Q(
                occurrences__end_at__isnull=True,
                occurrences__start_at__gte=now,
                occurrences__is_cancelled=False,
            )
        )
        .distinct()
        .select_related(
            "location",
            "category",
        )
        .prefetch_related(
            Prefetch(
                "occurrences",
                queryset=valid_dates,
                to_attr="upcoming_dates",
            )
        )
    )


# =========================================================
# Available trips
# =========================================================

def available_trips():

    today = timezone.localdate().isoformat()

    return (
        TouristSpot.objects
        .filter(
            status=TouristSpot.Status.PUBLISHED,
        )
        .exclude(
            spot_type=TouristSpot.SpotType.OFFER,
            details__validThrough__lt=today,
        )
    )


# =========================================================
# Event card data
# =========================================================

def make_event_card(event):

    next_date = (
        event.upcoming_dates[0].start_at
        if event.upcoming_dates
        else None
    )

    return {
        "kind": "event",
        "id": event.pk,

        "title": event.title,
        "summary": event.summary_ja,

        "image_url": event.image_url,
        "image_credit": "",
        "image_source_url": "",
        "image_license_url": "",
        "image_is_ai": False,
        "has_image": bool(event.image_url),

        "label": "イベント",

        "date": next_date,
        "created_at": event.created_at,

        "location": (
            event.location.city
            if event.location
            else ""
        ),

        "score": 0,
    }


# =========================================================
# Trip card data
# =========================================================

def make_trip_card(spot):

    details = spot.details or {}

    approved_image = (
        details.get("approved_image") or {}
    )

    image_url = ""
    image_credit = ""
    image_source_url = ""
    image_license_url = ""
    image_is_ai = False

    # =====================================================
    # 1. Wikimedia Commons image
    # =====================================================

    # 手動承認した写真と、
    # 自動検索で選ばれた写真の両方に対応する。
    #
    # reviewed=True:
    #   人間が確認した写真
    #
    # selection_method="automatic":
    #   自動検索で選択した写真

    if (
        approved_image.get("image_type") == "wikimedia"
        and approved_image.get("url")
        and (
            approved_image.get("reviewed") is True
            or approved_image.get("selection_method")
            == "automatic"
        )
    ):

        image_url = approved_image["url"]

        image_credit = approved_image.get(
            "credit",
            "",
        )

        image_source_url = approved_image.get(
            "source_url",
            "",
        )

        image_license_url = approved_image.get(
            "license_url",
            "",
        )

    # =====================================================
    # 2. Temporary local AI image for Arosa
    # =====================================================

    # Wikimedia Commonsの写真がない場合だけ、
    # 以前生成したArosaのAI画像を使う。
    #
    # 今後はAI画像もDB管理に変更する予定。

    elif (
        spot.spot_type
        == TouristSpot.SpotType.DESTINATION
        and spot.title_original.strip().lower()
        == "arosa"
    ):

        image_url = static(
            "outings/images/ai/arosa.webp"
        )

        image_credit = "AI生成イメージ"
        image_is_ai = True

    # =====================================================
    # Build trip card
    # =====================================================

    return {
        "kind": "trip",
        "id": spot.pk,

        "title": (
            spot.title_ja
            or spot.title_original
        ),

        "summary": spot.summary_ja,

        # Image
        "image_url": image_url,
        "image_credit": image_credit,
        "image_source_url": image_source_url,
        "image_license_url": image_license_url,
        "image_is_ai": image_is_ai,
        "has_image": bool(image_url),

        # Spot information
        "label": spot.get_spot_type_display(),

        "date": None,
        "created_at": spot.imported_at,
        "location": "",

        "score": spot.ai_quality_score or 0,
    }


# =========================================================
# Mix event and trip cards
# =========================================================

def interleave_cards(events, trips):

    """
    イベントと旅行を交互に並べる。

    どちらか一方だけでHOMEが
    埋まらないようにする。
    """

    result = []

    longest = max(
        len(events),
        len(trips),
    )

    for index in range(longest):

        if index < len(events):
            result.append(
                events[index]
            )

        if index < len(trips):
            result.append(
                trips[index]
            )

    return result


# =========================================================
# Unified HOME
# =========================================================

def home(request):

    now = timezone.now()

    visitor_id = get_visitor_id(request)

    # =====================================================
    # Events
    # =====================================================

    events = available_events()

    # -------------------------
    # New events
    # -------------------------

    new_events = list(
        events
        .order_by(
            "-created_at",
            "-pk",
        )[:12]
    )

    # -------------------------
    # Recommended events
    # -------------------------

    # 既存のFEATURED掲載区分を使用。
    # イベントの個人設定を考慮したおすすめは
    # 今後統合予定。

    recommended_events = list(
        events
        .filter(
            listing_tier=Event.ListingTier.FEATURED,
        )
        .annotate(
            next_start=Min(
                "occurrences__start_at",
                filter=Q(
                    occurrences__is_cancelled=False,
                    occurrences__start_at__gte=now,
                ),
            )
        )
        .order_by(
            "next_start",
            "pk",
        )[:12]
    )

    # =====================================================
    # Trips
    # =====================================================

    trips = available_trips()

    # -------------------------
    # New trips
    # -------------------------

    new_trips = list(
        trips
        .order_by(
            "-imported_at",
            "-pk",
        )[:12]
    )

    # -------------------------
    # Recommended trips
    # -------------------------

    recommended_trips = list(
        trips
        .filter(
            ai_quality_score__gte=70,
        )
        .order_by(
            "-ai_quality_score",
            "-imported_at",
            "pk",
        )[:12]
    )

    # =====================================================
    # Prepare mixed cards
    # =====================================================

    fresh_cards = interleave_cards(
        [
            make_event_card(event)
            for event in new_events
        ],
        [
            make_trip_card(spot)
            for spot in new_trips
        ],
    )

    recommended_cards = interleave_cards(
        [
            make_event_card(event)
            for event in recommended_events
        ],
        [
            make_trip_card(spot)
            for spot in recommended_trips
        ],
    )

    # =====================================================
    # Collect displayed IDs
    # =====================================================

    all_cards = (
        fresh_cards
        + recommended_cards
    )

    visible_event_ids = {
        card["id"]
        for card in all_cards
        if card["kind"] == "event"
    }

    visible_trip_ids = {
        card["id"]
        for card in all_cards
        if card["kind"] == "trip"
    }

    # =====================================================
    # Event hearts
    # =====================================================

    hearted_event_ids = set(
        EventHeart.objects
        .filter(
            visitor_id=visitor_id,
            event_id__in=visible_event_ids,
        )
        .values_list(
            "event_id",
            flat=True,
        )
    )

    # =====================================================
    # Trip hearts
    # =====================================================

    hearted_trip_ids = set(
        TouristSpotHeart.objects
        .filter(
            visitor_id=visitor_id,
            spot_id__in=visible_trip_ids,
        )
        .values_list(
            "spot_id",
            flat=True,
        )
    )

    # =====================================================
    # Mark hearted cards
    # =====================================================

    # 同じ記事が新着とおすすめの両方に
    # 表示される場合も状態を統一する。

    for card in all_cards:

        if card["kind"] == "event":

            card["hearted"] = (
                card["id"] in hearted_event_ids
            )

        else:

            card["hearted"] = (
                card["id"] in hearted_trip_ids
            )

    # =====================================================
    # Render
    # =====================================================

    response = render(
        request,
        "outings/home.html",
        {
            "fresh_cards": fresh_cards,
            "recommended_cards": recommended_cards,
            "fresh_preview_count": 6,
            "recommended_preview_count": 6,
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )


# =========================================================
# Unified saved items
# =========================================================

def saved_all(request):

    visitor_id = get_visitor_id(request)

    selected_type = request.GET.get("type", "all")

    if selected_type not in (
        "all",
        "event",
        "trip",
    ):
        selected_type = "all"

    # =====================================================
    # Saved events
    # =====================================================

    event_ids = list(
        EventHeart.objects
        .filter(visitor_id=visitor_id)
        .order_by("-pk")
        .values_list("event_id", flat=True)
    )

    event_map = {
        event.pk: event
        for event in Event.objects.filter(
            pk__in=event_ids,
        ).select_related(
            "location",
            "category",
        )
    }

    saved_events = [
        event_map[event_id]
        for event_id in event_ids
        if event_id in event_map
    ]

    # =====================================================
    # Saved trips
    # =====================================================

    trip_ids = list(
        TouristSpotHeart.objects
        .filter(visitor_id=visitor_id)
        .order_by("-pk")
        .values_list("spot_id", flat=True)
    )

    trip_map = {
        spot.pk: spot
        for spot in TouristSpot.objects.filter(
            pk__in=trip_ids,
        )
    }

    saved_trips = [
        trip_map[spot_id]
        for spot_id in trip_ids
        if spot_id in trip_map
    ]

    # =====================================================
    # Cards
    # =====================================================

    event_cards = []

    for event in saved_events:

        card = {
            "kind": "event",
            "id": event.pk,
            "title": event.title,
            "summary": event.summary_ja or "",
            "image_url": event.image_url or "",
            "image_credit": "",
        }

        event_cards.append(card)

    trip_cards = []

    for spot in saved_trips:

        card = make_trip_card(spot)

        trip_cards.append(card)

    # =====================================================
    # Display selection
    # =====================================================

    if selected_type == "event":

        cards = event_cards

    elif selected_type == "trip":

        cards = trip_cards

    else:

        cards = interleave_cards(
            event_cards,
            trip_cards,
        )

    # =====================================================
    # Render
    # =====================================================

    response = render(
        request,
        "outings/saved_all.html",
        {
            "cards": cards,
            "selected_type": selected_type,
            "event_count": len(event_cards),
            "trip_count": len(trip_cards),
            "total_count": (
                len(event_cards) + len(trip_cards)
            ),
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )
