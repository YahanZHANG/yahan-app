"""Safe, conservative Eventfrog occurrence reconciliation.

Maps individual Eventfrog event IDs to existing Outings occurrences using exact
start timestamps. Missing events are NOT considered cancellations. Manual edits
are not overwritten except time updates backed by a stable Eventfrog ID.
"""
import csv
import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from outings.models import Event, EventOccurrence, EventSource, EventfrogOccurrenceLink

UTC = ZoneInfo('UTC')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def date_time(text):
    dt = parse_datetime(str(text or '').strip())
    return dt if dt is not None and timezone.is_aware(dt) else None


def truthy(value):
    return str(value or '').strip().casefold() in {'true', '1', 'yes'}


def eventfrog_ids(text):
    return [v.strip() for v in str(text or '').split('|') if v.strip()]


class Command(BaseCommand):
    help = 'Link Eventfrog IDs to occurrences and reconcile explicit cancellations/time changes.'

    def add_arguments(self, parser):
        parser.add_argument('--review', default='outings_audit/eventfrog_review_queue.csv')
        parser.add_argument('--snapshot', default='outings_audit/eventfrog_future_events_p1_to_p40.csv')
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **opts):
        review_path, snapshot_path = Path(opts['review']), Path(opts['snapshot'])
        for p in (review_path, snapshot_path):
            if not p.is_file():
                raise CommandError(f'Missing file: {p}')
        source = EventSource.objects.filter(name='Eventfrog').first()
        if source is None:
            raise CommandError('Eventfrog EventSource not found. Import events first.')

        snapshot_rows = read_csv(snapshot_path)
        source_by_id = {str(r.get('id', '')).strip(): r for r in snapshot_rows if r.get('id')}
        if not source_by_id:
            raise CommandError('Empty snapshot: refusing to reconcile')
        review_rows = read_csv(review_path)
        keys = {
            'series-' + hashlib.sha256((r.get('series_key') or '').encode('utf-8')).hexdigest()[:32]: r
            for r in review_rows if r.get('series_key')
        }
        events = {e.external_id: e for e in Event.objects.filter(source=source, external_id__in=keys).prefetch_related('occurrences')}
        plans = []
        missed = 0
        for stable, event in events.items():
            row = keys[stable]
            occurrences = {o.start_at.astimezone(UTC): o for o in event.occurrences.all()}
            for ext_id in eventfrog_ids(row.get('event_ids')):
                raw = source_by_id.get(ext_id)
                if raw is None:
                    missed += 1
                    continue
                begin = date_time(raw.get('begin'))
                if begin is None:
                    missed += 1
                    continue
                # A lookup by Eventfrog ID persists across future series or time changes.
                plans.append((event, occurrences, ext_id, begin.astimezone(UTC), raw))

        stats = {'new_links': 0, 'existing_links': 0, 'cancelled': 0, 'uncancelled': 0,
                 'moved': 0, 'ambiguous': 0, 'skipped': missed}
        # Fetch existing links for any IDs in snapshot, including explicitly cancelled
        # ones that were excluded from today's review list.
        ids = set(source_by_id)
        existing = EventfrogOccurrenceLink.objects.filter(eventfrog_id__in=ids).select_related('occurrence', 'event')
        by_id = {link.eventfrog_id: link for link in existing}
        all_actions = []
        for event, occurrences, ext_id, begin, raw in plans:
            link = by_id.get(ext_id)
            if link is not None:
                if link.event_id != event.id:
                    stats['ambiguous'] += 1
                    continue
                stats['existing_links'] += 1
                continue
            occurrence = occurrences.get(begin)
            if occurrence is None:
                stats['ambiguous'] += 1
                continue
            all_actions.append(('link', event, ext_id, occurrence, begin, raw))
            stats['new_links'] += 1

        # Reconcile ALL previously tracked IDs that are explicitly present in
        # today's raw API output. Missing IDs never imply cancellation.
        for ext_id, link in by_id.items():
            raw = source_by_id.get(ext_id)
            if not raw:
                continue
            is_cancelled = truthy(raw.get('cancelled'))
            start = date_time(raw.get('begin'))
            if start is None:
                continue
            start = start.astimezone(UTC)
            all_actions.append(('reconcile', link, start, is_cancelled))
            if is_cancelled and not link.occurrence.is_cancelled:
                stats['cancelled'] += 1
            elif not is_cancelled and link.occurrence.is_cancelled:
                stats['uncancelled'] += 1
            if link.occurrence.start_at.astimezone(UTC) != start:
                stats['moved'] += 1

        self.stdout.write('Eventfrog tracking: ' + ', '.join(f'{k}={v}' for k, v in stats.items()))
        self.stdout.write('No rows missing from Eventfrog are treated as cancelled.')
        if not opts['commit']:
            self.stdout.write('DRY RUN: no DB changes. Add --commit after reviewing counts.')
            return

        with transaction.atomic():
            for action in all_actions:
                if action[0] == 'link':
                    _, event, ext_id, occurrence, start, _raw = action
                    EventfrogOccurrenceLink.objects.get_or_create(
                        eventfrog_id=ext_id,
                        defaults={'event': event, 'occurrence': occurrence, 'last_source_start_at': start},
                    )
                else:
                    _, link, start, cancelled = action
                    occ = link.occurrence
                    # If multiple upstream IDs point to one local occurrence,
                    # a single upstream change cannot safely move/cancel it.
                    link_count = EventfrogOccurrenceLink.objects.filter(occurrence=occ).count()
                    if link_count != 1:
                        continue
                    changes = []
                    if occ.start_at.astimezone(UTC) != start:
                        collision = EventOccurrence.objects.filter(event=link.event, start_at=start).exclude(pk=occ.pk).exists()
                        if not collision:
                            occ.start_at = start
                            changes.append('start_at')
                    if occ.is_cancelled != cancelled:
                        occ.is_cancelled = cancelled
                        changes.append('is_cancelled')
                    if changes:
                        occ.save(update_fields=changes)
                    link.last_source_start_at = start
                    link.last_seen_at = timezone.now()
                    link.save(update_fields=['last_source_start_at', 'last_seen_at'])
        self.stdout.write(self.style.SUCCESS('Eventfrog occurrence tracking committed.'))
