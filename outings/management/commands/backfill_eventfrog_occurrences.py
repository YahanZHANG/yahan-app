"""Backfill missing local Eventfrog dates using reviewed series and a frozen raw snapshot.

Dry-run by default. Never delete/move/cancel existing occurrences and never invoke APIs.
"""
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from outings.models import Event, EventOccurrence, EventfrogOccurrenceLink, EventSource


def load(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def parsed(value):
    dt = parse_datetime((value or '').strip())
    if dt is None or timezone.is_naive(dt):
        return None
    return dt


def truthy(value):
    return str(value or '').strip().lower() in {'true', '1', 'yes'}


class Command(BaseCommand):
    help = 'Safely add missing future occurrences for already-published Eventfrog series.'

    def add_arguments(self, parser):
        parser.add_argument('--review', default='outings_audit/eventfrog_review_queue.csv')
        parser.add_argument('--snapshot', default='outings_audit/eventfrog_current_45days.csv')
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **options):
        review_path = Path(options['review'])
        snapshot_path = Path(options['snapshot'])
        if not review_path.is_file() or not snapshot_path.is_file():
            raise CommandError('Review or snapshot CSV not found. No changes made.')
        reviews = load(review_path)
        raws = {str(r.get('id', '')).strip(): r for r in load(snapshot_path) if r.get('id')}
        if not reviews or not raws:
            raise CommandError('Empty review or snapshot. No changes made.')
        source = EventSource.objects.filter(name='Eventfrog').first()
        if source is None:
            raise CommandError('Eventfrog source not found')

        now = timezone.now()
        counters = Counter()
        actions = []
        examples = []
        seen = set()
        for row in reviews:
            key = (row.get('series_key') or '').strip()
            if not key:
                continue
            stable = 'series-' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:32]
            event = Event.objects.filter(source=source, external_id=stable,
                                         status=Event.Status.PUBLISHED).first()
            if event is None:
                counters['not_published'] += 1
                continue
            # Only add starts which are explicitly present in this run's reviewed series.
            reviewed_starts = set()
            for value in (row.get('occurrence_starts') or '').split('|'):
                if value.strip():
                    dt = parsed(value)
                    if dt is not None:
                        reviewed_starts.add(dt)
            if not reviewed_starts:
                counters['no_review_dates'] += 1
                continue
            candidates = defaultdict(list)
            for ext_id in (row.get('event_ids') or '').split('|'):
                ext_id = ext_id.strip()
                raw = raws.get(ext_id)
                if not raw:
                    continue
                start = parsed(raw.get('begin'))
                if (start is None or start <= now or start not in reviewed_starts
                        or truthy(raw.get('cancelled'))
                        or str(raw.get('visible', '')).strip().lower() == 'false'
                        or str(raw.get('published', '')).strip().lower() == 'false'):
                    continue
                candidates[start].append(ext_id)

            for start, ids in candidates.items():
                if len(ids) != 1:
                    counters['ambiguous_same_start'] += 1
                    continue
                ext_id = ids[0]
                pair = (event.pk, start)
                if pair in seen:
                    continue
                seen.add(pair)
                link = EventfrogOccurrenceLink.objects.filter(eventfrog_id=ext_id).first()
                if link is not None:
                    if link.event_id != event.pk or link.occurrence.start_at != start:
                        counters['conflicting_link'] += 1
                    else:
                        counters['already_linked'] += 1
                    continue
                existing = EventOccurrence.objects.filter(event=event, start_at=start).first()
                if existing:
                    if existing.is_cancelled or EventfrogOccurrenceLink.objects.filter(occurrence=existing).exists():
                        counters['existing_unlinked_ambiguous'] += 1
                    else:
                        actions.append(('link_only', event, existing, start, ext_id))
                        counters['link_only'] += 1
                else:
                    actions.append(('create', event, None, start, ext_id))
                    counters['new_dates'] += 1
                    if len(examples) < 15:
                        examples.append((event.pk, event.title, str(start), ext_id))

        for key in ('new_dates', 'link_only', 'already_linked', 'not_published',
                    'ambiguous_same_start', 'conflicting_link', 'existing_unlinked_ambiguous'):
            self.stdout.write(f'{key}: {counters[key]}')
        for example in examples:
            self.stdout.write(f'  ADD event={example[0]} {example[1][:50]} start={example[2]} id={example[3]}')
        if not options['commit']:
            self.stdout.write('DRY RUN: no DB changes; no API calls or AI usage.')
            return
        with transaction.atomic():
            for action, event, existing, start, ext_id in actions:
                if EventfrogOccurrenceLink.objects.filter(eventfrog_id=ext_id).exists():
                    raise CommandError(f'Concurrent Eventfrog ID conflict: {ext_id}')
                occurrence, _ = EventOccurrence.objects.get_or_create(
                    event=event, start_at=start,
                    defaults={'end_at': None, 'is_cancelled': False},
                )
                if occurrence.is_cancelled or EventfrogOccurrenceLink.objects.filter(occurrence=occurrence).exists():
                    raise CommandError(f'Concurrent occurrence conflict: {occurrence.pk}')
                EventfrogOccurrenceLink.objects.create(
                    eventfrog_id=ext_id, event=event, occurrence=occurrence,
                    last_source_start_at=start,
                )
        self.stdout.write(self.style.SUCCESS(f'Committed: {counters["new_dates"]} new dates, '
                                                 f'{counters["link_only"]} new links.'))
