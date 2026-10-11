"""Apply explicit Eventfrog cancellations from a scanner status CSV.

Usage:
  python manage.py sync_eventfrog_cancellations --file outings_audit/eventfrog_status_p1_to_p3.csv
  python manage.py sync_eventfrog_cancellations --file outings_audit/eventfrog_status_p1_to_p40.csv --commit

Dry-run by default. Never treats missing IDs as cancelled, never deletes rows,
and never automatically reactivates cancelled dates.
"""
import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from outings.models import EventfrogOccurrenceLink, EventOccurrence


def is_true(value):
    return str(value or '').strip().casefold() in {'true', '1', 'yes'}


class Command(BaseCommand):
    help = 'Cancel only uniquely tracked Eventfrog occurrences explicitly marked cancelled=true.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='CSV from scan_eventfrog_future status export')
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.is_file():
            raise CommandError(f'CSV not found: {path}')
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            mandatory = {'eventfrog_id', 'cancelled', 'begin', 'checked_at'}
            if not mandatory.issubset(reader.fieldnames or []):
                raise CommandError(f'Missing columns: {mandatory - set(reader.fieldnames or [])}')
            rows = list(reader)
        if not rows:
            raise CommandError('Empty status CSV; no changes made')

        by_id = {}
        contradictory = set()
        for row in rows:
            ext_id = (row.get('eventfrog_id') or '').strip()
            if not ext_id:
                continue
            if ext_id in by_id and is_true(by_id[ext_id].get('cancelled')) != is_true(row.get('cancelled')):
                contradictory.add(ext_id)
            by_id[ext_id] = row
        cancelled_ids = {k for k, v in by_id.items() if is_true(v.get('cancelled'))} - contradictory
        links = {
            link.eventfrog_id: link
            for link in EventfrogOccurrenceLink.objects.filter(eventfrog_id__in=cancelled_ids)
            .select_related('occurrence', 'event')
        }
        counter = Counter()
        actions = []
        for ext_id in sorted(cancelled_ids):
            link = links.get(ext_id)
            if not link:
                counter['not_tracked'] += 1
                continue
            occurrence = link.occurrence
            if occurrence.event_id != link.event_id:
                counter['inconsistent_link'] += 1
                continue
            if EventfrogOccurrenceLink.objects.filter(occurrence=occurrence).exclude(pk=link.pk).exists():
                counter['shared_occurrence_held'] += 1
                continue
            row = by_id[ext_id]
            source_begin = parse_datetime(row.get('begin') or '')
            if source_begin is None or source_begin.tzinfo is None:
                counter['invalid_source_begin'] += 1
                continue
            if occurrence.is_cancelled:
                counter['already_cancelled'] += 1
                continue
            # The Eventfrog ID is stable across a time change. Cancelling a
            # uniquely linked occurrence does not require matching dates.
            actions.append((ext_id, occurrence.pk, link.event_id, occurrence.start_at))
            counter['to_cancel'] += 1
        self.stdout.write(f'Status CSV rows: {len(rows)}, unique IDs: {len(by_id)}')
        self.stdout.write(f'Explicit cancelled IDs: {len(cancelled_ids)}, contradictory IDs held: {len(contradictory)}')
        for key in ('to_cancel', 'already_cancelled', 'not_tracked', 'shared_occurrence_held',
                    'inconsistent_link', 'invalid_source_begin'):
            self.stdout.write(f'{key}: {counter[key]}')
        for ext_id, pk, event_id, start in actions[:20]:
            self.stdout.write(f'  CANCEL occurrence={pk} event={event_id} Eventfrog={ext_id} start={start}')
        if not options['commit']:
            self.stdout.write('DRY RUN: DB unchanged. Add --commit only after reviewing the actions.')
            return
        with transaction.atomic():
            for ext_id, occ_id, event_id, original_start in actions:
                link = EventfrogOccurrenceLink.objects.select_for_update().get(eventfrog_id=ext_id)
                occ = EventOccurrence.objects.select_for_update().get(pk=occ_id)
                if (link.occurrence_id != occ_id or link.event_id != event_id
                    or occ.event_id != event_id or occ.start_at != original_start
                    or EventfrogOccurrenceLink.objects.filter(occurrence_id=occ_id).count() != 1):
                    raise CommandError('Data changed while syncing; transaction rolled back.')
                if not occ.is_cancelled:
                    occ.is_cancelled = True
                    occ.save(update_fields=['is_cancelled'])
        self.stdout.write(self.style.SUCCESS(f'Committed explicit cancellations: {len(actions)}'))
        self.stdout.write('Missing IDs were ignored. No dates were deleted or automatically reactivated.')
