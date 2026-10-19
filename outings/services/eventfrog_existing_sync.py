"""Safely reconcile KNOWN Eventfrog occurrence IDs against an API snapshot.

Never infer cancellation from absence in a limited-date/paginated response.
Never touch member submissions or an event with a manually protected status.
"""
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from outings.models import Event, EventOccurrence, EventfrogOccurrenceLink


def _aware(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return parsed if timezone.is_aware(parsed) else None


def sync_existing(events, *, commit=False):
    """events: list from eventfrog.collect(), before grouping.

    Returns count dict. Dates of a linked occurrence are updated in place so
    comments/links don't lose their foreign keys. Colliding dates are skipped.
    """
    indexed = {str(e.get('id')): e for e in events if e.get('id')}
    links = list(EventfrogOccurrenceLink.objects.select_related('event', 'occurrence').filter(eventfrog_id__in=indexed))
    stats = {'matched': len(links), 'changed_dates': 0, 'changed_details': 0, 'skipped': 0}
    for link in links:
        event = link.event
        if event.source_id is None or event.source.name.lower() != 'eventfrog' or event.status not in (Event.Status.PUBLISHED, Event.Status.DRAFT):
            stats['skipped'] += 1
            continue
        upstream = indexed[link.eventfrog_id]
        new_start, new_end = _aware(upstream.get('start')), _aware(upstream.get('end'))
        if not new_start or not new_end or new_end <= new_start:
            stats['skipped'] += 1
            continue
        occ = link.occurrence
        update_date = (occ.start_at != new_start or occ.end_at != new_end)
        if update_date:
            conflict = EventOccurrence.objects.filter(event_id=event.pk, start_at=new_start).exclude(pk=occ.pk).exists()
            if conflict:
                stats['skipped'] += 1
                continue
        if update_date:
            stats['changed_dates'] += 1
        if commit and update_date:
            with transaction.atomic():
                if update_date:
                    occ.start_at = new_start
                    occ.end_at = new_end
                    occ.save(update_fields=['start_at', 'end_at'])
                    link.last_source_start_at = new_start
                    link.save(update_fields=['last_source_start_at', 'last_seen_at'])
    return stats


def apply_cancellations(cancelled_ids, *, commit=False):
    """Mark linked occurrences cancelled when Eventfrog explicitly flags them.

    Only an explicit `cancelled` flag counts; an ID missing from the snapshot
    is never treated as a cancellation.
    """
    links = (
        EventfrogOccurrenceLink.objects
        .select_related('event', 'event__source', 'occurrence')
        .filter(eventfrog_id__in=[str(i) for i in cancelled_ids], occurrence__is_cancelled=False)
    )
    stats = {'cancelled': 0, 'skipped': 0}
    for link in links:
        event = link.event
        if (
            link.occurrence_id is None
            or event.source_id is None
            or event.source.name.lower() != 'eventfrog'
            or event.status not in (Event.Status.PUBLISHED, Event.Status.DRAFT)
        ):
            stats['skipped'] += 1
            continue
        stats['cancelled'] += 1
        if commit:
            EventOccurrence.objects.filter(pk=link.occurrence_id).update(is_cancelled=True)
    return stats
