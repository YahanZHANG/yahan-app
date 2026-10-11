
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from django.db import transaction

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import EventSubmissionForm

from .models import (
    Event,
    EventCategory,
    EventLocation,
    EventOccurrence,
    EventTag,
    EventHeart, 
    OutingsPreference,
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


def home(request):

    now = timezone.now()
    today = timezone.localdate()

    saturday, sunday, weekend_start, weekend_end = (
        get_weekend_range(today)
    )

    category_slug = request.GET.get("category", "").strip()
    tag_slug = request.GET.get("tag", "").strip()

    # 公開中かつ、今後の開催が存在するイベント
    base_events = (
        Event.objects.filter(
            status=Event.Status.PUBLISHED,
            occurrences__is_cancelled=False,
            occurrences__end_at__gt=now,
        )
        .select_related("category", "location")
        .distinct()
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
            end_at__gt=now,
        )
        .order_by("start_at")
    )

    weekend_occurrences = (
        upcoming_occurrences.filter(
            start_at__lt=weekend_end,
            end_at__gt=weekend_start,
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

    weekend_events = sorted(
        (
            event
            for event in events
            if event.weekend_dates
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

    context = {
        "weekend_events": weekend_events,
        "upcoming_events": upcoming_events,
        "weekend_start": saturday,
        "weekend_end": sunday,
        "categories": categories,
        "active_category": active_category,
        "active_tag": active_tag,
        "is_filtered": bool(category_slug or tag_slug),
        "recommended_events": recommended_events,
        "personalization_enabled": personalization_enabled,
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


def event_detail(request, pk):

    event = get_object_or_404(
        Event.objects.select_related(
            "category",
            "location",
            "source",
        ).prefetch_related(
            "tags",
            "occurrences",
        ),
        pk=pk,
        status=Event.Status.PUBLISHED,
    )

    visitor_id = get_visitor_id(request)

    is_hearted = EventHeart.objects.filter(
        event=event,
        visitor_id=visitor_id,
    ).exists()

    heart_count = EventHeart.objects.filter(
        event=event,
    ).count()

    response = render(
        request,
        "outings/event_detail.html",
        {
            "event": event,
            "is_hearted": is_hearted,
            "heart_count": heart_count,
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
        reverse("outings:my_page")
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
        OutingsNotification,
        pk=pk,
        recipient=request.user,
    )

    if not notification.is_read:
        notification.is_read = True
        notification.save(
            update_fields=["is_read"]
        )

    if (
        notification.event_id
        and notification.event
        and notification.event.status
            == Event.Status.PUBLISHED
    ):
        return redirect(
            "outings:event_detail",
            pk=notification.event_id,
        )

    return redirect(
        "outings:my_notifications"
    )


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
