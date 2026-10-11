
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from outings.models import (
    Event,
    EventLocation,
    EventOccurrence,
    EventSource,
)


SWISS_TIMEZONE = ZoneInfo("Europe/Zurich")


def save_collected_event(item, commit=False):
    """
    Return: (status, event_id)

    status:
      INVALID
      REVIEW
      EXISTS
      DRY_RUN
      CREATED

    Existing events are never modified.
    """

    if (
        not item.title
        or not item.external_id
        or not item.original_url
    ):
        return "INVALID", None

    if item.warnings:
        return "REVIEW", None

    if (
        item.start_at is None
        or item.end_at is None
        or not item.venue
    ):
        return "REVIEW", None

    start_at = item.start_at
    end_at = item.end_at

    if timezone.is_naive(start_at):
        start_at = timezone.make_aware(
            start_at,
            SWISS_TIMEZONE,
        )

    if timezone.is_naive(end_at):
        end_at = timezone.make_aware(
            end_at,
            SWISS_TIMEZONE,
        )

    if end_at <= start_at:
        return "INVALID", None

    source = EventSource.objects.filter(
        name=item.source_name,
        is_active=True,
    ).first()

    if source is None:
        return "INVALID", None

    existing = Event.objects.filter(
        source=source,
        external_id=item.external_id,
    ).first()

    if existing:
        return "EXISTS", existing.pk

    if not commit:
        return "DRY_RUN", None

    with transaction.atomic():

        location, _ = EventLocation.objects.get_or_create(
            name=item.venue,
            city=item.city,
            canton=item.canton,
        )

        # Import only as draft, never directly published.
        # Preserve unknown fee as text; do not publish
        # until it has been reviewed.

        fee_known_free = item.is_free is True

        event, created = Event.objects.get_or_create(
            source=source,
            external_id=item.external_id,
            defaults={
                "title": item.title,
                "title_original": item.title,
                "summary_ja": "",
                "description_original": item.description,
                "event_type": Event.EventType.ONE_TIME,
                "status": Event.Status.DRAFT,
                "location": location,
                "is_free": fee_known_free,
                "price_text": (
                    "無料"
                    if fee_known_free
                    else "料金未確認・要確認"
                ),
                "original_url": item.original_url,
            },
        )

        if not created:
            return "EXISTS", event.pk

        EventOccurrence.objects.get_or_create(
            event=event,
            start_at=start_at,
            defaults={
                "end_at": end_at,
            },
        )

        return "CREATED", event.pk
