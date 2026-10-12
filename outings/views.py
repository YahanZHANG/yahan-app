from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from django.db import transaction

from django.db.models import Count, Prefetch, Q, Min, Max
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .forms import EventSubmissionForm, OutingsCommentForm

from .models import (
    Event,
    EventCategory,
    EventLocation,
    EventOccurrence,
    EventTag,
    EventHeart, 
    OutingsPreference,
    OutingsComment,
    OutingsNotification
)

from .visitor import get_visitor_id, set_visitor_cookie





def get_weekend_range(today):



    # 月〜日を単位として今週末を計算。

    # 日曜日は今日を含む週末を対象にする。

    days_until_saturday = (5 - today.weekday()) % 7



    if today.weekday() == 6:

        saturday = today - timedelta(days=1)

    else:

        saturday = today + timedelta(days=days_until_saturday)



    sunday = saturday + timedelta(days=1)



    start = timezone.make_aware(

        datetime.combine(saturday, time.min)

    )



    end = timezone.make_aware(

        datetime.combine(

            sunday + timedelta(days=1),

            time.min,

        )

    )



    return saturday, sunday, start, end





def get_event_emoji(event):

    """

    イベントのカテゴリーとタイトルから絵文字を選択する。

    """



    title = (

        (event.title or "") + " "

        + (event.title_original or "")

    ).lower()



    keywords = [

        (["weihnacht", "christmas", "クリスマス"], "🎄"),

        (["halloween", "ハロウィン"], "🎃"),

        (["baby", "ベビー", "赤ちゃん"], "👶"),

        (["kind", "子ども", "こども", "親子"], "🧸"),

        (["markt", "market", "マーケット"], "🛍️"),

        (["festival", "fest", "祭り", "フェス"], "🎪"),

        (["museum", "美術館", "博物館"], "🏛️"),

        (["kunst", "art", "アート", "絵画"], "🎨"),

        (["musik", "music", "konzert", "音楽"], "🎵"),

        (["theater", "劇", "舞台"], "🎭"),

        (["essen", "food", "グルメ", "料理"], "🍽️"),

        (["wander", "山", "ハイキング"], "🥾"),

        (["natur", "nature", "自然"], "🌿"),

        (["sport", "スポーツ"], "⚽"),

        (["workshop", "体験", "ワークショップ"], "✂️"),

        (["schloss", "castle", "城"], "🏰"),

    ]



    for words, emoji in keywords:

        if any(word in title for word in words):

            return emoji



    category_emojis = {

        "festival": "🎪",

        "art": "🎨",

        "music": "🎵",

        "food": "🍽️",

        "outdoor": "🌿",

        "sports": "⚽",

        "workshop": "✂️",

        "sightseeing": "🏔️",

    }



    if event.category:

        return category_emojis.get(event.category.slug, "🎈")



    return "🎈"



def home(request):



    now = timezone.now()

    seven_days_later = now + timedelta(days=7)

    today = timezone.localdate()



    saturday, sunday, weekend_start, weekend_end = (

        get_weekend_range(today)

    )



    category_slug = request.GET.get("category", "").strip()

    tag_slug = request.GET.get("tag", "").strip()



        # =====================================================

    # Region filter

    # =====================================================



    region = request.GET.get("region", "").strip().upper()



    regions = [

        ("ZH", "Zürich"),

        ("AG", "Aargau"),

        ("BS", "Basel-Stadt"),

        ("BL", "Basel-Landschaft"),

        ("ZG", "Zug"),

        ("LU", "Luzern"),

        ("BE", "Bern"),

    ]



    valid_regions = {code for code, name in regions}



    if region not in valid_regions:

        region = ""





    # 管理者は ?preview=1 でDRAFTも確認できる

    preview_mode = (

        request.user.is_authenticated

        and request.user.is_staff

        and request.GET.get("preview") == "1"

    )



    visible_statuses = [Event.Status.PUBLISHED]



    if preview_mode:

        visible_statuses.append(Event.Status.DRAFT)



    # 終了日時が未登録でも、開始日時が未来なら表示対象

    valid_occurrence = (

        Q(occurrences__end_at__gt=now)

        | Q(

            occurrences__end_at__isnull=True,

            occurrences__start_at__gte=now,

        )

    )



    base_events = (

        Event.objects.filter(

            status__in=visible_statuses,

            occurrences__is_cancelled=False,

        )

        .filter(valid_occurrence)

        .select_related("category", "location")

        .distinct()

    )



    if region:

        base_events = base_events.filter(

            location__canton=region

        )





    if category_slug:

        base_events = base_events.filter(

            category__slug=category_slug,

            category__is_active=True,

        )



    if tag_slug:

        base_events = base_events.filter(

            tags__slug=tag_slug,

        )



    # 現在公開可能な開催日時

    upcoming_occurrences = (

        EventOccurrence.objects.filter(

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



    weekend_occurrences = (

        upcoming_occurrences

        .filter(

            start_at__gte=now,

            start_at__lt=seven_days_later,

        )

    )



    events = list(

        base_events.prefetch_related(

            "tags",

            Prefetch(

                "occurrences",

                queryset=upcoming_occurrences,

                to_attr="upcoming_dates",

            ),

            Prefetch(

                "occurrences",

                queryset=weekend_occurrences,

                to_attr="weekend_dates",

            ),

        )

    )



    for event in events:

        event.display_emoji = get_event_emoji(event)





    # =====================================================

    # 今後7日以内のイベント（14日以上の長期開催は除外）

    # =====================================================



    event_ids = [event.pk for event in events]



    event_spans = {

        row["event_id"]: row

        for row in (

            EventOccurrence.objects

            .filter(

                event_id__in=event_ids,

                is_cancelled=False,

            )

            .values("event_id")

            .annotate(

                first_date=Min("start_at"),

                last_date=Max("start_at"),

            )

        )

    }



    def is_long_running(event):

        span = event_spans.get(event.pk)



        if not span:

            return False



        first_date = span["first_date"]

        last_date = span["last_date"]



        if not first_date or not last_date:

            return False



        return (

            last_date - first_date

        ) >= timedelta(days=14)



    weekend_events = sorted(

        (

            event

            for event in events

            if event.weekend_dates

            and not is_long_running(event)

        ),

        key=lambda event: event.weekend_dates[0].start_at,

    )[:12]



    upcoming_events = sorted(

        (

            event

            for event in events

            if event.upcoming_dates

        ),

        key=lambda event: event.upcoming_dates[0].start_at,

    )[:30]



    # 暫定おすすめ

    # 将来的にハート・お気に入り地域などで選定する



    visitor_id = get_visitor_id(request)



    preference = OutingsPreference.objects.filter(

        visitor_id=visitor_id

    ).first()



    favorite_regions = (

        preference.favorite_regions

        if preference else []

    )



    hearted_events = list(

        Event.objects.filter(

            hearts__visitor_id=visitor_id

        ).prefetch_related("tags")

    )



    liked_category_ids = {

        event.category_id

        for event in hearted_events

        if event.category_id

    }



    liked_tag_ids = {

        tag.id

        for event in hearted_events

        for tag in event.tags.all()

    }



    personalization_enabled = (

        preference.personalization_enabled

        if preference else True

    )



    scored_events = []



    for event in upcoming_events:



        score = 0



        if personalization_enabled:



            if (

                event.location

                and event.location.canton in favorite_regions

            ):

                score += 5



            if event.category_id in liked_category_ids:

                score += 4



            matching_tags = sum(

                1

                for tag in event.tags.all()

                if tag.id in liked_tag_ids

            )



            score += matching_tags * 3



        scored_events.append((score, event))



    scored_events.sort(

        key=lambda item: (

            -item[0],

            item[1].upcoming_dates[0].start_at,

        )

    )



    recommended_events = [

        event

        for score, event in scored_events[:6]

    ]





    categories = EventCategory.objects.filter(

        is_active=True

    ).order_by("sort_order", "name")



    active_category = None



    if category_slug:

        active_category = categories.filter(

            slug=category_slug

        ).first()



    active_tag = None



    if tag_slug:

        active_tag = EventTag.objects.filter(

            slug=tag_slug

        ).first()


    # =====================================================
    # Featured eligibility
    # Long-running / regularly recurring events
    # =====================================================

    occurrence_rows = (
        EventOccurrence.objects
        .filter(
            event_id__in=[e.pk for e in events],
            is_cancelled=False,
        )
        .values(
            "event_id",
            "start_at",
            "end_at",
        )
        .order_by("start_at")
    )

    occurrence_data = {}

    for row in occurrence_rows:
        occurrence_data.setdefault(
            row["event_id"], []
        ).append(row)

    def is_featured_ineligible(event):

        rows = occurrence_data.get(event.pk, [])

        if not rows:
            return False

        # Individual occurrence lasting at least 14 days.
        for row in rows:

            start = row["start_at"]
            end = row["end_at"]

            if (
                start
                and end
                and end - start >= timedelta(days=14)
            ):
                return True

        # All distinct scheduled calendar dates.
        dates = sorted({
            timezone.localtime(
                row["start_at"]
            ).date()
            for row in rows
            if row["start_at"]
        })

        if len(dates) < 2:
            return False

        # Overall scheduled span of at least 14 days.
        if (dates[-1] - dates[0]).days >= 14:
            return True

        # Weekly or biweekly repetitions.
        if any(
            (later - earlier).days in (7, 14)
            for earlier, later in zip(
                dates,
                dates[1:],
            )
        ):
            return True

        return False


    # =====================================================
    # Editorial tiers
    # =====================================================

    featured_events = []
    standard_events = []
    compact_events = []
    community_events = []

    for event in events:

        if not event.upcoming_dates:
            continue

        # Member-submitted events belong in Community.
        if event.source_id is None:
            community_events.append(event)
            continue

        if event.listing_tier == Event.ListingTier.FEATURED:

            if is_featured_ineligible(event):
                # Keep published, but show in Event Information.
                standard_events.append(event)
            else:
                featured_events.append(event)

        elif event.listing_tier == Event.ListingTier.STANDARD:
            standard_events.append(event)

        elif event.listing_tier == Event.ListingTier.COMPACT:
            compact_events.append(event)

    # Keep the existing chronological ordering.
    for event_list in (
        featured_events,
        standard_events,
        compact_events,
        community_events,
    ):
        event_list.sort(
            key=lambda e: e.upcoming_dates[0].start_at
        )

    # =====================================================
    # Hearted event IDs for HOME cards
    # =====================================================

    hearted_ids = set(
        EventHeart.objects.filter(
            visitor_id=visitor_id,
            event_id__in=[event.pk for event in events],
        ).values_list("event_id", flat=True)
    )

    context = {
        "featured_events": featured_events[:24],
        "standard_events": standard_events[:40],
        "compact_events": compact_events[:60],
        "community_events": community_events[:30],
        "weekend_events": weekend_events,
        "hearted_ids": hearted_ids,
        "upcoming_events": upcoming_events,
        "weekend_start": saturday,
        "weekend_end": sunday,
        "categories": categories,
        "active_category": active_category,
        "active_tag": active_tag,
        "is_filtered": bool(category_slug or tag_slug),
        "recommended_events": recommended_events,
        "personalization_enabled": personalization_enabled,
        "preview_mode": preview_mode,
        "draft_count": sum(
            event.status == Event.Status.DRAFT
            for event in events
        ),
        "regions": regions,
        "active_region": region,
        "is_filtered": bool(category_slug or tag_slug or region),
    }



    response = render(

        request,

        "outings/home.html",

        context,

    )



    return set_visitor_cookie(

        request,

        response,

        visitor_id,

    )



def search(request):

    now = timezone.now()

    # =====================================================
    # Regions
    # =====================================================

    regions = [
        ("ZH", "Zürich"),
        ("AG", "Aargau"),
        ("BS", "Basel-Stadt"),
        ("BL", "Basel-Landschaft"),
        ("ZG", "Zug"),
        ("LU", "Luzern"),
        ("BE", "Bern"),
    ]

    valid_regions = {code for code, name in regions}

    region = request.GET.get(
        "region", ""
    ).strip().upper()

    if region not in valid_regions:
        region = ""

    # =====================================================
    # Categories
    # =====================================================

    categories = EventCategory.objects.filter(
        is_active=True
    ).order_by("sort_order", "name")

    category = request.GET.get(
        "category", ""
    ).strip()

    valid_categories = set(
        categories.values_list("slug", flat=True)
    )

    if category not in valid_categories:
        category = ""

    # =====================================================
    # Other filters
    # =====================================================

    family_only = (
        request.GET.get("tag") == "family"
    )

    query = request.GET.get(
        "q", ""
    ).strip()[:100]

    # =====================================================
    # Date filters
    # =====================================================

    date_from = request.GET.get(
        "date_from", ""
    ).strip()

    date_to = request.GET.get(
        "date_to", ""
    ).strip()

    start_date = (
        parse_date(date_from)
        if date_from
        else None
    )

    end_date = (
        parse_date(date_to)
        if date_to
        else None
    )

    # Invalid dates are ignored.
    if start_date is None:
        date_from = ""

    if end_date is None:
        date_to = ""

    # If the dates are reversed, swap them.
    if (
        start_date is not None
        and end_date is not None
        and start_date > end_date
    ):
        start_date, end_date = (
            end_date,
            start_date,
        )

        date_from = start_date.isoformat()
        date_to = end_date.isoformat()

    # Convert local calendar dates to aware datetimes.
    #
    # Start: 00:00 on the selected date
    # End:   00:00 on the day AFTER the selected date
    #
    # Exclusive upper bound avoids issues with seconds,
    # microseconds and daylight-saving transitions.

    tz = timezone.get_current_timezone()

    range_start = None
    range_end = None

    if start_date:
        range_start = timezone.make_aware(
            datetime.combine(
                start_date,
                time.min,
            ),
            tz,
        )

    if end_date:
        range_end = timezone.make_aware(
            datetime.combine(
                end_date + timedelta(days=1),
                time.min,
            ),
            tz,
        )

    # =====================================================
    # Staff preview
    # =====================================================

    preview_mode = (
        request.user.is_authenticated
        and request.user.is_staff
        and request.GET.get("preview") == "1"
    )

    statuses = [Event.Status.PUBLISHED]

    if preview_mode:
        statuses.append(Event.Status.DRAFT)

    # =====================================================
    # Eligible occurrences
    # =====================================================

    # Occurrences must still be ongoing or upcoming.
    #
    # Events with no end_at are considered point-in-time
    # events for the purposes of searching.

    occurrence_filter = (
        Q(is_cancelled=False)
        &
        (
            Q(end_at__gt=now)
            | Q(
                end_at__isnull=True,
                start_at__gte=now,
            )
        )
    )

    # Date range overlap:
    #
    # occurrence_start < selected_range_end
    # AND
    # occurrence_end > selected_range_start
    #
    # For occurrences without end_at, use start_at.

    if range_start is not None:
        occurrence_filter &= (
            Q(end_at__gt=range_start)
            | Q(
                end_at__isnull=True,
                start_at__gte=range_start,
            )
        )

    if range_end is not None:
        occurrence_filter &= Q(
            start_at__lt=range_end
        )

    # =====================================================
    # Matching occurrences
    # =====================================================

    matching_dates = (
        EventOccurrence.objects
        .filter(occurrence_filter)
        .order_by("start_at")
    )

    matching_event_ids = (
        matching_dates
        .values("event_id")
    )

    # =====================================================
    # Event queryset
    # =====================================================

    events = (
        Event.objects
        .filter(
            status__in=statuses,
            pk__in=matching_event_ids,
        )
        .select_related(
            "location",
            "category",
        )
    )

    # =====================================================
    # Region filter
    # =====================================================

    if region:
        events = events.filter(
            location__canton=region
        )

    # =====================================================
    # Category filter
    # =====================================================

    if category:
        events = events.filter(
            category__slug=category,
            category__is_active=True,
        )

    # =====================================================
    # Family filter
    # =====================================================

    if family_only:
        events = events.filter(
            tags__slug="family"
        )

    # =====================================================
    # Keyword search
    # =====================================================

    if query:
        events = events.filter(
            Q(title__icontains=query)
            | Q(title_original__icontains=query)
            | Q(summary_ja__icontains=query)
            | Q(location__city__icontains=query)
            | Q(location__name__icontains=query)
        )

    # =====================================================
    # Sort by first matching occurrence
    # =====================================================

    events = (
        events
        .distinct()
        .annotate(
            next_start=Min(
                "occurrences__start_at",
                filter=Q(
                    occurrences__in=matching_dates
                ),
            )
        )
        .order_by(
            "next_start",
            "pk",
        )
        .prefetch_related(
            Prefetch(
                "occurrences",
                queryset=matching_dates,
                to_attr="search_dates",
            )
        )
    )

    # =====================================================
    # Pagination
    # =====================================================

    paginator = Paginator(events, 20)

    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    # =====================================================
    # Emoji
    # =====================================================

    for event in page_obj.object_list:
        event.display_emoji = (
            get_event_emoji(event)
        )

    # =====================================================
    # Context
    # =====================================================

    context = {
        "events": page_obj.object_list,
        "page_obj": page_obj,
        "result_count": paginator.count,

        "regions": regions,
        "active_region": region,

        "categories": categories,
        "active_category": category,

        "family_only": family_only,
        "query": query,
        "preview_mode": preview_mode,

        "date_from": date_from,
        "date_to": date_to,
    }

    return render(
        request,
        "outings/search.html",
        context,
    )


def event_detail(request, pk):



    # 公開イベントは全員閲覧可能。

    # 管理者はDRAFTも閲覧可能。

    # 一般投稿者は自分の投稿も閲覧可能。

    if request.user.is_authenticated and request.user.is_staff:

        visibility_filter = Q(

            status__in=[

                Event.Status.PUBLISHED,

                Event.Status.DRAFT,

            ]

        )

    elif request.user.is_authenticated:

        visibility_filter = (

            Q(status=Event.Status.PUBLISHED)

            | Q(

                created_by=request.user,

                source__isnull=True,

            )

        )

    else:

        visibility_filter = Q(

            status=Event.Status.PUBLISHED

        )



    event = get_object_or_404(

        Event.objects.select_related(

            "category",

            "location",

            "source",

        ).prefetch_related(

            "tags",

            "occurrences",

        ).filter(visibility_filter),

        pk=pk,

    )





    visitor_id = get_visitor_id(request)



    is_hearted = EventHeart.objects.filter(

        event=event,

        visitor_id=visitor_id,

    ).exists()



    heart_count = EventHeart.objects.filter(

        event=event,

    ).count()



    reply_queryset = (

        OutingsComment.objects.filter(

            parent__isnull=False,

        )

        .select_related("author")

        .order_by("created_at", "pk")

    )



    comments = (

        OutingsComment.objects.filter(

            event=event,

            parent__isnull=True,

        )

        .select_related("author")

        .prefetch_related(

            Prefetch(

                "replies",

                queryset=reply_queryset,

            )

        )

        .order_by("created_at", "pk")

    )



    comment_count = OutingsComment.objects.filter(

        event=event,

        is_deleted=False,

    ).count()



    if request.user.is_authenticated:

        for comment in comments:

            comment.can_delete = (

                request.user.pk == comment.author_id

                or request.user.pk == event.created_by_id

                or request.user.is_staff

            )

            comment.can_edit = (

                request.user.pk == comment.author_id

                and not comment.is_deleted

            )



            for reply in comment.replies.all():

                reply.can_delete = (

                    request.user.pk == reply.author_id

                    or request.user.pk == event.created_by_id

                    or request.user.is_staff

                )

                reply.can_edit = (

                    request.user.pk == reply.author_id

                    and not reply.is_deleted

                )



    response = render(

        request,

        "outings/event_detail.html",

        {

            "event": event,

            "is_hearted": is_hearted,

            "heart_count": heart_count,

            "comments": comments,

            "comment_count": comment_count,

            "comment_form": OutingsCommentForm(),

        },

    )



    return set_visitor_cookie(

        request,

        response,

        visitor_id,

    )





@require_POST

def toggle_heart(request, pk):



    event = get_object_or_404(

        Event,

        pk=pk,

        status=Event.Status.PUBLISHED,

    )



    visitor_id = get_visitor_id(request)



    heart, created = EventHeart.objects.get_or_create(

        event=event,

        visitor_id=visitor_id,

    )



    if not created:

        heart.delete()



    response = HttpResponseRedirect(

        reverse(

            "outings:event_detail",

            args=[event.pk],

        )

    )



    return set_visitor_cookie(

        request,

        response,

        visitor_id,

    )





def my_page(request):



    visitor_id = get_visitor_id(request)



    preference, created = (

        OutingsPreference.objects.get_or_create(

            visitor_id=visitor_id,

        )

    )



    hearted_events = (

        Event.objects.filter(

            hearts__visitor_id=visitor_id,

            status=Event.Status.PUBLISHED,

        )

        .select_related("location", "category")

        .order_by("-hearts__created_at")

    )



    my_post_count = 0

    unread_notification_count = 0



    if request.user.is_authenticated:



        my_post_count = Event.objects.filter(

            created_by=request.user,

        ).count()



        unread_notification_count = (

            OutingsNotification.objects.filter(

                recipient=request.user,

                is_read=False,

            ).count()

        )



    response = render(

        request,

        "outings/my_page.html",

        {

            "hearted_events": hearted_events,

            "heart_count": hearted_events.count(),

            "preference": preference,

            "my_post_count": my_post_count,

            "unread_notification_count": unread_notification_count,

        },

    )



    return set_visitor_cookie(

        request,

        response,

        visitor_id,

    )

# =========================================================
# Saved events
# =========================================================

def saved_events(request):

    visitor_id = get_visitor_id(request)

    hearted_events = (
        Event.objects.filter(
            hearts__visitor_id=visitor_id,
            status=Event.Status.PUBLISHED,
        )
        .select_related("location", "category")
        .order_by("-hearts__created_at")
    )

    response = render(
        request,
        "outings/saved_events.html",
        {
            "hearted_events": hearted_events,
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )


# =========================================================
# My preferences
# =========================================================

def my_preferences(request):

    visitor_id = get_visitor_id(request)

    preference, created = (
        OutingsPreference.objects.get_or_create(
            visitor_id=visitor_id,
        )
    )

    regions = [
        ("ZH", "Zürich"),
        ("AG", "Aargau"),
        ("BS", "Basel-Stadt"),
        ("BL", "Basel-Landschaft"),
        ("ZG", "Zug"),
        ("LU", "Luzern"),
        ("BE", "Bern"),
        ("SZ", "Schwyz"),
        ("SO", "Solothurn"),
        ("NW", "Nidwalden"),
        ("OW", "Obwalden"),
    ]

    response = render(
        request,
        "outings/my_preferences.html",
        {
            "preference": preference,
            "regions": regions,
        },
    )

    return set_visitor_cookie(
        request,
        response,
        visitor_id,
    )



@require_POST

def save_preferences(request):



    visitor_id = get_visitor_id(request)



    preference, created = (

        OutingsPreference.objects.get_or_create(

            visitor_id=visitor_id,

        )

    )



    allowed_regions = {

        "ZH", "BS", "BL", "ZG", "LU",

        "AG", "SZ", "SO", "NW", "OW",

    }



    regions = [

        region

        for region in request.POST.getlist("regions")

        if region in allowed_regions

    ]



    preference.favorite_regions = regions

    preference.personalization_enabled = (

        request.POST.get("personalization") == "on"

    )

    preference.save()



    response = HttpResponseRedirect(
        reverse("outings:my_preferences")
    )



    return set_visitor_cookie(

        request,

        response,

        visitor_id,

    )





# =========================================================

# Notifications

# =========================================================



@login_required

def my_notifications(request):



    notifications = (

        OutingsNotification.objects.filter(

            recipient=request.user,

        )

        .select_related(

            "actor",

            "event",

        )

        .order_by("-created_at", "-pk")

    )



    paginator = Paginator(notifications, 20)



    page_obj = paginator.get_page(

        request.GET.get("page", 1)

    )



    return render(

        request,

        "outings/my_notifications.html",

        {

            "page_obj": page_obj,

        },

    )







@login_required

@require_POST

def notification_open(request, pk):



    notification = get_object_or_404(

        OutingsNotification.objects.select_related(

            "event",

            "comment",

        ),

        pk=pk,

        recipient=request.user,

    )



    if not notification.is_read:

        notification.is_read = True

        notification.save(

            update_fields=["is_read"]

        )



    event = notification.event



    if (

        event is None

        or event.status != Event.Status.PUBLISHED

    ):

        return redirect("outings:my_notifications")



    url = reverse(

        "outings:event_detail",

        kwargs={"pk": event.pk},

    )



    if notification.comment_id:

        url += f"#comment-{notification.comment_id}"



    return redirect(url)





# =========================================================

# Submit Event

# =========================================================



@login_required

def event_create(request):



    form = EventSubmissionForm(

        request.POST if request.method == "POST" else None

    )



    if request.method == "POST" and form.is_valid():



        with transaction.atomic():



            location = EventLocation.objects.create(

                name=form.cleaned_data["venue_name"],

                address=form.cleaned_data["address"],

                city=form.cleaned_data["city"],

                canton=form.cleaned_data["canton"],

            )



            event = form.save(commit=False)



            event.location = location

            event.created_by = request.user



            # 投稿者が公開状態を変更することはできない

            event.status = Event.Status.PENDING



            # ユーザー投稿は外部API収集と区別する

            event.source = None

            event.external_id = ""



            event.save()

            form.save_m2m()



            EventOccurrence.objects.create(

                event=event,

                start_at=form.cleaned_data["start_at"],

                end_at=form.cleaned_data["end_at"],

            )



        return redirect("outings:my_posts")



    return render(

        request,

        "outings/event_form.html",

        {

            "form": form,

        },

    )





# =========================================================

# My Event Posts

# =========================================================



@login_required

def my_posts(request):



    posts = (

        Event.objects.filter(

            created_by=request.user,

        )

        .select_related(

            "category",

            "location",

        )

        .order_by("-created_at", "-pk")

    )



    paginator = Paginator(posts, 20)



    page_obj = paginator.get_page(

        request.GET.get("page", 1)

    )



    return render(

        request,

        "outings/my_posts.html",

        {

            "page_obj": page_obj,

        },

    )







# =========================================================

# Edit own event

# =========================================================



@login_required

def event_edit(request, pk):



    event = get_object_or_404(

        Event,

        pk=pk,

        created_by=request.user,

    )



    # 現段階では1開催日時の投稿だけ編集対象

    if event.occurrences.count() != 1:

        return render(

            request,

            "outings/event_edit_unavailable.html",

            {"event": event},

        )



    form = EventSubmissionForm(

        request.POST if request.method == "POST" else None,

        instance=event,

    )



    if request.method == "POST" and form.is_valid():



        with transaction.atomic():



            # 会場は新規作成して、他イベントとの

            # 共有データを誤って変更しない

            location = EventLocation.objects.create(

                name=form.cleaned_data["venue_name"],

                address=form.cleaned_data["address"],

                city=form.cleaned_data["city"],

                canton=form.cleaned_data["canton"],

            )



            updated_event = form.save(commit=False)



            updated_event.location = location



            # 投稿者や外部イベント情報は変更しない

            updated_event.created_by = request.user



            # 再審査を必須にする

            updated_event.status = Event.Status.PENDING



            updated_event.save()

            form.save_m2m()



            occurrence = updated_event.occurrences.get()



            occurrence.start_at = form.cleaned_data["start_at"]

            occurrence.end_at = form.cleaned_data["end_at"]

            occurrence.save()



        return redirect("outings:my_posts")



    return render(

        request,

        "outings/event_form.html",

        {

            "form": form,

            "is_edit": True,

            "event": event,

        },

    )





# =========================================================

# Delete own event

# =========================================================



@login_required

def event_delete(request, pk):



    event = get_object_or_404(

        Event,

        pk=pk,

        created_by=request.user,

    )



    if request.method == "POST":

        event.delete()

        return redirect("outings:my_posts")



    return render(

        request,

        "outings/event_confirm_delete.html",

        {"event": event},

    )







# =========================================================

# Outings Comments

# =========================================================



@login_required

@require_POST

def comment_create(request, pk):



    event = get_object_or_404(

        Event,

        pk=pk,

        status=Event.Status.PUBLISHED,

    )



    parent_id = request.POST.get("parent", "").strip()

    parent = None



    if parent_id:

        parent = get_object_or_404(

            OutingsComment,

            pk=parent_id,

            event=event,

            parent__isnull=True,

            is_deleted=False,

        )



    form = OutingsCommentForm(request.POST)



    if not form.is_valid():

        messages.error(

            request,

            "コメントを確認して。500文字以内で入力してね。",

        )

        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": event.pk},

            ) + "#comments"

        )



    # 30秒以内の連続コメントを制限

    recent_comment = OutingsComment.objects.filter(

        author=request.user,

        created_at__gte=(

            timezone.now() - timedelta(seconds=30)

        ),

    ).exists()



    if recent_comment:

        messages.error(

            request,

            "連続投稿を防ぐため、30秒以上空けて投稿して。",

        )

        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": event.pk},

            ) + "#comments"

        )



    with transaction.atomic():



        comment = form.save(commit=False)

        comment.event = event

        comment.author = request.user

        comment.parent = parent

        comment.save()



        recipients = {}



        # イベント投稿者に通知

        if (

            event.created_by_id

            and event.created_by_id != request.user.pk

        ):

            recipients[event.created_by_id] = (

                OutingsNotification.Kind.COMMENT

            )



        # 返信先の作者に通知

        if (

            parent is not None

            and parent.author_id != request.user.pk

        ):

            recipients[parent.author_id] = (

                OutingsNotification.Kind.REPLY

            )



        for recipient_id, kind in recipients.items():



            OutingsNotification.objects.create(

                recipient_id=recipient_id,

                actor=request.user,

                event=event,

                comment=comment,

                kind=kind,

                message=(

                    "コメントに返信が届いた。"

                    if kind == OutingsNotification.Kind.REPLY

                    else "イベントに新しいコメントが届いた。"

                ),

            )



    return redirect(

        reverse(

            "outings:event_detail",

            kwargs={"pk": event.pk},

        ) + f"#comment-{comment.pk}"

    )





# =========================================================

# Edit own comment

# =========================================================



@login_required

def comment_edit(request, pk):



    comment = get_object_or_404(

        OutingsComment.objects.select_related("event"),

        pk=pk,

        author=request.user,

        is_deleted=False,

        event__status=Event.Status.PUBLISHED,

    )



    form = OutingsCommentForm(

        request.POST if request.method == "POST" else None,

        instance=comment,

    )



    if request.method == "POST" and form.is_valid():



        form.save()



        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": comment.event_id},

            ) + f"#comment-{comment.pk}"

        )



    return render(

        request,

        "outings/comment_form.html",

        {

            "form": form,

            "comment": comment,

        },

    )





# =========================================================

# Soft delete comment

# =========================================================



@login_required

def comment_delete(request, pk):



    comment = get_object_or_404(

        OutingsComment.objects.select_related("event"),

        pk=pk,

        is_deleted=False,

        event__status=Event.Status.PUBLISHED,

    )



    event = comment.event



    can_delete = (

        request.user.pk == comment.author_id

        or request.user.pk == event.created_by_id

        or request.user.is_staff

    )



    if not can_delete:

        raise Http404



    if request.method == "POST":



        reason = request.POST.get(

            "reason", ""

        ).strip()[:200]



        if not reason:

            if request.user.pk == comment.author_id:

                reason = "本人による削除"

            elif request.user.is_staff:

                reason = "管理者による削除"

            else:

                reason = "イベント投稿者による削除"



        comment.is_deleted = True

        comment.deleted_at = timezone.now()

        comment.deleted_by = request.user

        comment.deleted_reason = reason



        comment.save(

            update_fields=[

                "is_deleted",

                "deleted_at",

                "deleted_by",

                "deleted_reason",

                "updated_at",

            ]

        )



        # 削除されたコメントを指す未読通知は既読化

        OutingsNotification.objects.filter(

            comment=comment,

            is_read=False,

        ).update(is_read=True)



        return redirect(

            reverse(

                "outings:event_detail",

                kwargs={"pk": event.pk},

            ) + f"#comment-{comment.pk}"

        )



    return render(

        request,

        "outings/comment_confirm_delete.html",

        {

            "comment": comment,

            "event": event,

        },

    )





# =========================================================

# My Comments

# =========================================================



@login_required

def my_comments(request):



    comments = (

        OutingsComment.objects.filter(

            author=request.user,

            is_deleted=False,

            event__status=Event.Status.PUBLISHED,

        )

        .select_related("event")

        .order_by("-created_at", "-pk")

    )



    paginator = Paginator(comments, 20)



    page_obj = paginator.get_page(

        request.GET.get("page", 1)

    )



    return render(

        request,

        "outings/my_comments.html",

        {

            "page_obj": page_obj,

        },

    )
